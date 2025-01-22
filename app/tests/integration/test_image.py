# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Image test module."""

import glob
import logging

# Subprocess is used to run the application.
import subprocess  # nosec: B404
import urllib.parse
from pathlib import Path

import pytest
import pytest_asyncio
from click.testing import CliRunner
from fabric.connection import Connection as SSHConnection
from openstack.compute.v2.image import Image
from openstack.compute.v2.server import Server
from openstack.connection import Connection
from openstack.network.v2.security_group import SecurityGroup
from pylxd import Client

from github_runner_image_builder.cli import get_latest_build_id
from github_runner_image_builder.config import IMAGE_OUTPUT_PATH
from tests.integration import commands, helpers, types

logger = logging.getLogger(__name__)


@pytest_asyncio.fixture(scope="module", name="openstack_server")
async def openstack_server_fixture(
    openstack_metadata: types.OpenstackMeta,
    openstack_security_group: SecurityGroup,
    openstack_image_name: str,
    test_id: str,
):
    """A testing openstack instance."""
    server_name = f"test-server-{test_id}"
    images: list[Image] = openstack_metadata.connection.search_images(openstack_image_name)
    assert images, "No built image found."
    for server in helpers.create_openstack_server(
        openstack_metadata=openstack_metadata,
        server_name=server_name,
        image=images[0],
        security_group=openstack_security_group,
    ):
        yield server

    for image in images:
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


@pytest.fixture(scope="module", name="cli_run")
def cli_run_fixture(
    image: str,
    cloud_name: str,
    callback_script: Path,
    openstack_connection: Connection,
    openstack_image_name: str,
):
    """A CLI run.

    This fixture assumes pipx is installed in the system and the github-runner-image-builder has
    been installed using pipx. See testenv:integration section of tox.ini.
    """
    # This is a locally built application - we can trust it.
    subprocess.check_call(  # nosec: B603
        ["/usr/bin/sudo", Path.home() / ".local/bin/github-runner-image-builder", "init"]
    )
    subprocess.check_call(  # nosec: B603
        [
            "/usr/bin/sudo",
            Path.home() / ".local/bin/github-runner-image-builder",
            "run",
            cloud_name,
            openstack_image_name,
            "--base-image",
            image,
            "--keep-revisions",
            "2",
            "--callback-script",
            str(callback_script.absolute()),
        ]
    )

    yield

    openstack_image: Image
    for openstack_image in openstack_connection.search_images(openstack_image_name):
        openstack_connection.delete_image(openstack_image.id)
    for image_file in glob.glob("*.img"):
        Path(image_file).unlink(missing_ok=True)


@pytest.mark.asyncio
@pytest.mark.amd64
@pytest.mark.usefixtures("cli_run")
async def test_image_amd(
    image: str, tmp_path: Path, dockerhub_mirror: urllib.parse.ParseResult | None
):
    """
    arrange: given a built output from the CLI.
    act: when the image is booted and commands are executed.
    assert: commands do not error.
    """
    lxd = Client()
    logger.info("Creating LXD VM Image.")
    helpers.create_lxd_vm_image(
        lxd_client=lxd, img_path=IMAGE_OUTPUT_PATH, image=image, tmp_path=tmp_path
    )
    logger.info("Launching LXD instance.")
    instance = await helpers.create_lxd_instance(lxd_client=lxd, image=image)

    for testcmd in commands.TEST_RUNNER_COMMANDS:
        if testcmd.external:
            continue
        if testcmd.name == "configure dockerhub mirror":
            if not dockerhub_mirror:
                continue
            testcmd.command = helpers.format_dockerhub_mirror_microk8s_command(
                command=testcmd.command, dockerhub_mirror=dockerhub_mirror
            )
        logger.info("Running command: %s", testcmd.command)
        # run command as ubuntu user. Passing in user argument would not be equivalent to a login
        # shell which is missing critical environment variables such as $USER and the user groups
        # are not properly loaded.
        result = instance.execute(
            ["su", "--shell", "/bin/bash", "--login", "ubuntu", "-c", testcmd.command]
        )
        logger.info("Command output: %s %s %s", result.exit_code, result.stdout, result.stderr)
        assert result.exit_code == 0


@pytest.mark.amd64
@pytest.mark.arm64
@pytest.mark.asyncio
@pytest.mark.usefixtures("cli_run")
async def test_openstack_upload(openstack_connection: Connection, openstack_image_name: str):
    """
    arrange: given a built output from the CLI.
    act: when openstack images are listed.
    assert: the built image is uploaded in Openstack.
    """
    assert len(openstack_connection.search_images(openstack_image_name))


@pytest.mark.arm64
@pytest.mark.asyncio
@pytest.mark.usefixtures("cli_run")
async def test_image_arm(
    ssh_connection: SSHConnection, dockerhub_mirror: urllib.parse.ParseResult | None
):
    """
    arrange: given a built output from the CLI.
    act: when the image is booted and commands are executed.
    assert: commands do not error.
    """
    helpers.run_openstack_tests(dockerhub_mirror=dockerhub_mirror, ssh_connection=ssh_connection)


@pytest.mark.amd64
@pytest.mark.arm64
@pytest.mark.asyncio
@pytest.mark.usefixtures("cli_run")
async def test_script_callback(callback_result_path: Path):
    """
    arrange: given a CLI run with script that creates a file.
    act: None.
    assert: the file exist.
    """
    assert callback_result_path.exists()
    assert len(callback_result_path.read_text(encoding="utf-8"))


@pytest.mark.amd64
@pytest.mark.arm64
@pytest.mark.asyncio
@pytest.mark.usefixtures("cli_run")
async def test_get_image(
    cloud_name: str,
    openstack_image_name: str,
    openstack_connection: Connection,
):
    """
    arrange: a cli that already ran.
    act: when get image id is run.
    assert: the latest image matches the stdout output.
    """
    result = CliRunner().invoke(get_latest_build_id, args=[cloud_name, openstack_image_name])
    image_id = openstack_connection.get_image_id(openstack_image_name)

    assert (
        result.output == image_id
    ), f"Openstack image not matching, {result.output} {result.exit_code}, {image_id}"
