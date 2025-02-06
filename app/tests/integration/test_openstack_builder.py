# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test openstack image builder module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

import functools
import itertools
import logging
import subprocess
import typing
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from fabric.connection import Connection as SSHConnection
from openstack.compute.v2.image import Image
from openstack.compute.v2.server import Server
from openstack.connection import Connection
from openstack.network.v2.security_group import SecurityGroup

from github_runner_image_builder import config, openstack_builder
from tests.integration import helpers, types

logger = logging.getLogger(__name__)

# The timeout is increased to 15 minutes to account for the slow testing infrastructure.
openstack_builder.CREATE_SERVER_TIMEOUT = 15 * 60


@pytest.mark.amd64
@pytest.mark.arm64
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

    # This is a locally built application - we can trust it.
    subprocess.check_call(  # nosec: B603
        [
            "/usr/bin/sudo",
            Path.home() / ".local/bin/github-runner-image-builder",
            "init",
            "--cloud",
            cloud_name,
            "--prefix",
            prefix,
        ]
    )

    # 1.
    images: list[Image] = openstack_connection.list_images()
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
    image_builder_images = itertools.chain(jammy_images, noble_images)
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
    callback_script: Path,
    dockerhub_mirror_url: str,
) -> list[str]:
    """A CLI run.

    This fixture assumes pipx is installed in the system and the github-runner-image-builder has
    been installed using pipx. See testenv:integration section of tox.ini.
    """
    openstack_image_name = f"{test_id}-image-builder-test"
    cli_args = [
        "/usr/bin/sudo",
        Path.home() / ".local/bin/github-runner-image-builder",
        "run",
        openstack_metadata.cloud_name,
        openstack_image_name,
        "--base-image",
        image_config.image,
        "--keep-revisions",
        "1",
        "--arch",
        image_config.arch.value,
        "--callback-script",
        str(callback_script.absolute()),
        "--flavor",
        openstack_metadata.flavor,
        "--network",
        openstack_metadata.network,
        "--prefix",
        test_id,
        "--script-url",
        "https://raw.githubusercontent.com/canonical/github-runner-image-builder/"
        "eb0ca315bf8c7aa732b811120cbabca4b8d16216/tests/integration/testdata/"
        "test_script.sh",
        "--upload-clouds",
        openstack_metadata.cloud_name,
    ]
    if proxy.http:
        cli_args.extend(["--proxy", proxy.http])
    if dockerhub_mirror_url:
        cli_args.extend(["--dockerhub-cache", dockerhub_mirror_url])

    stdout = subprocess.check_output(
        cli_args,  # nosec: B603,
        env={
            "IMAGE_BUILDER_TEST_SECRET": "SHOULD_EXIST",
            "IMAGE_BUILDER_TEST_NON_SECRET": "SHOULD_NOT_EXIST",
        },
    )
    image_ids = str(stdout)
    return image_ids.split(",")


@pytest.fixture(scope="module", name="make_dangling_resources")
async def make_dangling_resources_fixture(
    openstack_metadata: types.OpenstackMeta, test_id: str, image_config: types.ImageConfig
):
    """Make OpenStack resources that imitates failed run."""
    keypair = openstack_metadata.connection.create_keypair(
        openstack_builder._get_keypair_name(prefix=test_id)
    )
    server = openstack_metadata.connection.create_server(
        name=openstack_builder._get_builder_name(
            arch=image_config.arch, base=config.BaseImage(image_config.image), prefix=test_id
        ),
        image=f"image-builder-base-jammy-{image_config.arch.value}",
        flavor=openstack_metadata.flavor,
        network=openstack_metadata.network,
        security_groups=[openstack_builder.SHARED_SECURITY_GROUP_NAME],
        wait=True,
    )

    yield

    openstack_metadata.connection.delete_keypair(name=keypair.name)
    openstack_metadata.connection.delete_server(name_or_id=server.id)


# the code is similar but the fixture source is localized and is different.
# pylint: disable=R0801
@pytest_asyncio.fixture(scope="module", name="openstack_server")
async def openstack_server_fixture(
    openstack_metadata: types.OpenstackMeta,
    openstack_security_group: SecurityGroup,
    test_id: str,
    image_ids: list[str],
):
    """A testing openstack instance."""
    image: Image = openstack_metadata.connection.get_image(name_or_id=image_ids[0])
    server_name = f"test-image-builder-run-{test_id}"
    for server in helpers.create_openstack_server(
        openstack_metadata=openstack_metadata,
        server_name=server_name,
        image=image,
        security_group=openstack_security_group,
    ):
        yield server
    openstack_metadata.connection.delete_image(image.id)


@pytest_asyncio.fixture(scope="module", name="ssh_connection")
async def ssh_connection_fixture(
    openstack_server: Server,
    proxy: types.ProxyConfig,
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
        proxy=proxy,
        dockerhub_mirror=dockerhub_mirror,
    )

    return ssh_connection


# pylint: enable=R0801


@pytest.mark.amd64
@pytest.mark.arm64
@pytest.mark.usefixtures("make_dangling_resources")
async def test_run(
    ssh_connection: SSHConnection, dockerhub_mirror: urllib.parse.ParseResult | None
):
    """
    arrange: given openstack cloud instance.
    act: when run (build image) is called.
    assert: an image snapshot of working VM is created with the ability to run expected commands.
    """
    helpers.run_openstack_tests(
        dockerhub_mirror=dockerhub_mirror, ssh_connection=ssh_connection, external=True
    )


@pytest.mark.amd64
@pytest.mark.arm64
async def test_openstack_state(
    openstack_metadata: types.OpenstackMeta, test_id: str, image_config: types.ImageConfig
):
    """
    arrange: given CLI run after dangling OpenStack resources creation.
    act: None.
    assert: Dangling resources are cleaned up.

    This test is dependent on the previons test_run test. Running a new test image building run
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


@pytest.mark.amd64
@pytest.mark.arm64
@pytest.mark.asyncio
async def test_script_callback(image_ids: list[str], callback_result_path: Path):
    """
    arrange: given a CLI run  with a script that creates a file.
    act: None.
    assert: the file contains the image ids produced by the run.
    """
    assert callback_result_path.exists()
    assert len(content := callback_result_path.read_text(encoding="utf-8"))
    assert ",".join(image_ids) in content
