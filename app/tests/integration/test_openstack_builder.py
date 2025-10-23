# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test openstack image builder module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

import functools
import itertools
import logging
import typing
import urllib.parse
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from fabric.connection import Connection as SSHConnection
from integration.helpers import TESTDATA_TEST_SCRIPT_URL
from openstack.compute.v2.image import Image
from openstack.compute.v2.server import Server
from openstack.connection import Connection
from openstack.network.v2.security_group import SecurityGroup

from github_runner_image_builder import config, openstack_builder
from github_runner_image_builder.openstack_builder import CREATE_SERVER_TIMEOUT
from tests.integration import helpers, types

logger = logging.getLogger(__name__)


def test_initialize(
    openstack_connection: Connection, arch: config.Arch, cloud_name: str, test_id: str
):
    """
    arrange: given an openstack cloud instance.
    act: when openstack builder is initialized.
    assert: \
        1. the base cloud images are created
        2. openstack resources(security group, keypair) are \
            created.
    """
    test_start_time = datetime.now(tz=timezone.utc)
    prefix = test_id

    openstack_builder.initialize(arch=arch, cloud_name=cloud_name, prefix=prefix)

    # 1.
    images: list[Image] = openstack_connection.list_images()
    focal_images = filter(
        functools.partial(
            helpers.has_name,
            name=openstack_builder._get_base_image_name(
                arch=arch, base=config.BaseImage.FOCAL, prefix=prefix
            ),
        ),
        images,
    )
    jammy_images = filter(
        functools.partial(
            helpers.has_name,
            name=openstack_builder._get_base_image_name(
                arch=arch, base=config.BaseImage.JAMMY, prefix=prefix
            ),
        ),
        images,
    )
    noble_images = filter(
        functools.partial(
            helpers.has_name,
            name=openstack_builder._get_base_image_name(
                arch=arch, base=config.BaseImage.NOBLE, prefix=prefix
            ),
        ),
        images,
    )
    image_builder_images = itertools.chain(focal_images, jammy_images, noble_images)
    test_images: typing.Iterable[Image] = filter(
        functools.partial(helpers.is_greater_than_time, timestamp=test_start_time),
        image_builder_images,
    )
    assert list(test_images)

    # 2.
    assert openstack_connection.get_security_group(
        name_or_id=openstack_builder.SHARED_SECURITY_GROUP_NAME
    )
    assert openstack_connection.get_keypair(
        name_or_id=openstack_builder._get_keypair_name(prefix=prefix)
    )


@pytest.fixture(scope="module", name="image_ids")
def image_ids_fixture(
    image_config: types.ImageConfig,
    openstack_metadata: types.OpenstackMeta,
    test_id: str,
    proxy: types.ProxyConfig,
) -> typing.Iterator[list[str]]:
    """A CLI run.

    This fixture assumes pipx is installed in the system and the github-runner-image-builder has
    been installed using pipx. See testenv:integration section of tox.ini.
    """
    try:
        image_ids = openstack_builder.run(
            cloud_config=openstack_builder.CloudConfig(
                cloud_name=openstack_metadata.cloud_name,
                flavor=openstack_metadata.flavor,
                network=openstack_metadata.network,
                proxy=proxy.http,
                prefix=test_id,
                upload_cloud_names=[openstack_metadata.cloud_name],
            ),
            image_config=config.ImageConfig(
                arch=image_config.arch,
                base=config.BaseImage.from_str(image_config.image),
                runner_version="",
                name=f"{test_id}-image-builder-test",
                script_config=config.ScriptConfig(
                    script_url=urllib.parse.urlparse(TESTDATA_TEST_SCRIPT_URL),
                    script_secrets={
                        "TEST_SECRET": "SHOULD_EXIST",
                        "TEST_NON_SECRET": "SHOULD_NOT_EXIST",
                    },
                ),
            ),
            keep_revisions=1,
        )
        yield image_ids.split(",")

    finally:
        # cleanup resources
        openstack_metadata.connection.delete_server(
            name_or_id=openstack_builder._get_builder_name(
                arch=image_config.arch, base=config.BaseImage(image_config.image), prefix=test_id
            )
        )
        openstack_metadata.connection.delete_keypair(
            name=openstack_builder._get_keypair_name(prefix=test_id)
        )


@pytest.fixture(scope="module", name="make_dangling_resources")
def make_dangling_resources_fixture(
    openstack_metadata: types.OpenstackMeta, test_id: str, image_config: types.ImageConfig
):
    """Make OpenStack resources that imitates failed run."""
    server = None
    try:
        builder_name = openstack_builder._get_builder_name(
            arch=image_config.arch, base=config.BaseImage(image_config.image), prefix=test_id
        )
        image_name = openstack_builder._get_base_image_name(
            arch=image_config.arch, base=config.BaseImage(image_config.image), prefix=test_id
        )
        server = openstack_metadata.connection.create_server(
            name=builder_name,
            image=image_name,
            flavor=openstack_metadata.flavor,
            network=openstack_metadata.network,
            security_groups=[openstack_builder.SHARED_SECURITY_GROUP_NAME],
            auto_ip=False,
            wait=True,
            timeout=CREATE_SERVER_TIMEOUT,
            # 2025/07/24 - This option is set to mitigate CVE-2024-6174
            config_drive=True,
        )

        yield
    finally:
        if server:
            openstack_metadata.connection.delete_server(name_or_id=server.id)


# the code is similar but the fixture source is localized and is different.
# pylint: disable=R0801
@pytest.fixture(scope="module", name="openstack_server")
def openstack_server_fixture(
    openstack_metadata: types.OpenstackMeta,
    openstack_security_group: SecurityGroup,
    test_id: str,
    image_ids: list[str],
):
    """A testing openstack instance."""
    image: Image = openstack_metadata.connection.get_image(name_or_id=image_ids[0])
    server_name = f"test-image-builder-run-{test_id}"
    yield from helpers.create_openstack_server(
        openstack_metadata=openstack_metadata,
        server_name=server_name,
        image=image,
        security_group=openstack_security_group,
    )
    openstack_metadata.connection.delete_image(image.id)


@pytest_asyncio.fixture(scope="module", name="ssh_connection")
async def ssh_connection_fixture(
    openstack_server: Server,
    openstack_metadata: types.OpenstackMeta,
    dockerhub_mirror: urllib.parse.ParseResult | None,
) -> SSHConnection:
    """The openstack server ssh connection fixture."""
    logger.info("Setting up SSH connection.")
    ssh_connection = await helpers.wait_for_valid_connection(
        connection_params=helpers.OpenStackConnectionParams(
            connection=openstack_metadata.connection,
            server_name=openstack_server.name,
            network=openstack_metadata.network,
            ssh_key=openstack_metadata.ssh_key.private_key,
        ),
        dockerhub_mirror=dockerhub_mirror,
    )

    return ssh_connection


@pytest.mark.usefixtures("make_dangling_resources")
def test_run(
    ssh_connection: SSHConnection,
    proxy: types.ProxyConfig,
):
    """
    arrange: given openstack cloud instance.
    act: when run (build image) is called.
    assert: an image snapshot of working VM is created with the ability to run expected commands.
    """
    if proxy.http is not None:
        helpers.setup_aproxy_disable_ipv6(ssh_connection, proxy.http)
    helpers.run_openstack_tests(ssh_connection=ssh_connection)


def test_openstack_state(
    openstack_metadata: types.OpenstackMeta, test_id: str, image_config: types.ImageConfig
):
    """
    arrange: given CLI run after dangling OpenStack resources creation.
    act: None.
    assert: Dangling resources are cleaned up.

    This test is dependent on the previous test_run test. Running a new test image building run
    is too costly at the moment.
    """
    server = openstack_metadata.connection.get_server(
        name_or_id=openstack_builder._get_builder_name(
            arch=image_config.arch, base=config.BaseImage(image_config.image), prefix=test_id
        )
    )
    assert not server, "Server not cleaned up."

    keypair = openstack_metadata.connection.get_keypair(
        name_or_id=openstack_builder._get_keypair_name(prefix=test_id)
    )
    assert keypair, "Keypair not exists."
