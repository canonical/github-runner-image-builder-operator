# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper utilities for integration tests."""

import collections
import dataclasses
import inspect
import logging
import platform
import tarfile
import time
import urllib.parse
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from string import Template
from typing import Awaitable, Callable, Generator, ParamSpec, Protocol, TypeVar, cast

import openstack.exceptions
import tenacity
from fabric import Connection as SSHConnection
from fabric import Result
from invoke.exceptions import UnexpectedExit
from openstack.compute.v2.image import Image as OpenstackImage
from openstack.compute.v2.server import Server
from openstack.connection import Connection
from openstack.network.v2.security_group import SecurityGroup
from paramiko.ssh_exception import NoValidConnectionsError, SSHException
from pylxd import Client
from pylxd.models.image import Image as LXDImage
from pylxd.models.instance import Instance, InstanceState
from requests_toolbelt import MultipartEncoder

from tests.integration import commands, types

logger = logging.getLogger(__name__)


TESTDATA_TEST_SCRIPT_URL = (
    "https://raw.githubusercontent.com/canonical/github-runner-image-builder-operator/"
    "cc9d06c43a5feabd278265ab580eca14d5acffd4/app/tests/integration/testdata/test_script.sh"
)


P = ParamSpec("P")
R = TypeVar("R")
S = Callable[P, R] | Callable[P, Awaitable[R]]


async def wait_for(
    func: S,
    timeout: int | float = 300,
    check_interval: int = 10,
) -> R:
    """Wait for function execution to become truthy.

    Args:
        func: A callback function to wait to return a truthy value.
        timeout: Time in seconds to wait for function result to become truthy.
        check_interval: Time in seconds to wait between ready checks.

    Raises:
        TimeoutError: if the callback function did not return a truthy value within timeout.

    Returns:
        The result of the function if any.
    """
    deadline = time.time() + timeout
    is_awaitable = inspect.iscoroutinefunction(func)
    while time.time() < deadline:
        if is_awaitable:
            if result := await cast(Awaitable, func()):
                return result
        else:
            if result := func():
                return cast(R, result)
        time.sleep(check_interval)

    # final check before raising TimeoutError.
    if is_awaitable:
        if result := await cast(Awaitable, func()):
            return result
    else:
        if result := func():
            return cast(R, result)
    raise TimeoutError()


def create_lxd_vm_image(
    lxd_client: Client, img_path: Path, image: str, tmp_path: Path
) -> LXDImage:
    """Create LXD VM image.

    1. Creates the metadata.tar.gz file with the corresponding Ubuntu OS image and a pre-defined
    templates directory. See testdata/templates.
    2. Uploads the created VM image to LXD - metadata and image of qcow2 format is required.
    3. Tags the uploaded image with an alias for test use.

    Args:
        lxd_client: PyLXD client.
        img_path: qcow2 (.img) file path to upload.
        tmp_path: Temporary dir.
        image: The Ubuntu image name.

    Returns:
        The created LXD image.
    """
    metadata_tar = _create_metadata_tar_gz(image=image, tmp_path=tmp_path)
    lxd_image = _post_vm_img(
        lxd_client, img_path.read_bytes(), metadata_tar.read_bytes(), public=True
    )
    lxd_image.add_alias(image, f"Ubuntu {image} {IMAGE_TO_TAG[image]} image.")
    return lxd_image


IMAGE_TO_TAG = {"focal": "20.04", "jammy": "22.04", "noble": "24.04"}


def _create_metadata_tar_gz(image: str, tmp_path: Path) -> Path:
    """Create metadata.tar.gz contents.

    Args:
        image: The ubuntu LTS image name.
        tmp_path: Temporary dir.

    Returns:
        The path to created metadata.tar.
    """
    # Create metadata.yaml
    template = Template(
        Path("tests/integration/testdata/metadata.yaml.tmpl").read_text(encoding="utf-8")
    )
    metadata_contents = template.substitute(
        {"arch": platform.machine(), "tag": IMAGE_TO_TAG[image], "image": image}
    )
    meta_path = tmp_path / "metadata.yaml"
    meta_path.write_text(metadata_contents, encoding="utf-8")

    # Pack templates/ and metada.yaml
    templates_path = Path("tests/integration/testdata/templates")
    metadata_tar = tmp_path / Path("metadata.tar.gz")

    with tarfile.open(metadata_tar, "w:gz") as tar:
        tar.add(meta_path, arcname=meta_path.name)
        tar.add(templates_path, arcname=templates_path.name)

    return metadata_tar


# This is a workaround until https://github.com/canonical/pylxd/pull/577 gets merged.
def _post_vm_img(
    client: Client,
    image_data: bytes,
    metadata: bytes | None = None,
    public: bool = False,
) -> LXDImage:
    """Create an LXD VM image.

    Args:
        client: The LXD client.
        image_data: Image qcow2 (.img) file contents in bytes.
        metadata: The metadata.tar.gz contents in bytes.
        public: Whether the image should be publicly available.

    Returns:
        The created LXD Image instance.
    """
    headers = {}
    if public:
        headers["X-LXD-Public"] = "1"

    if metadata is not None:
        # Image uploaded as chunked/stream (metadata, rootfs)
        # multipart message.
        # Order of parts is important metadata should be passed first
        files = collections.OrderedDict(
            {
                "metadata": ("metadata", metadata, "application/octet-stream"),
                # rootfs is container, rootfs.img is VM
                "rootfs.img": ("rootfs.img", image_data, "application/octet-stream"),
            }
        )
        data = MultipartEncoder(files)
        headers.update({"Content-Type": data.content_type})
    else:
        data = image_data

    response = client.api.images.post(data=data, headers=headers)
    operation = client.operations.wait_for_operation(response.json()["operation"])
    return LXDImage(client, fingerprint=operation.metadata["fingerprint"])


async def create_lxd_instance(lxd_client: Client, image: str) -> Instance:
    """Create and wait for LXD instance to become active.

    Args:
        lxd_client: PyLXD client.
        image: The Ubuntu image name.

    Returns:
        The created and running LXD instance.
    """
    instance_config = {
        "name": f"test-{image}",
        "source": {"type": "image", "alias": image},
        "type": "virtual-machine",
        "config": {"limits.cpu": "3", "limits.memory": "8192MiB"},
    }
    instance: Instance = lxd_client.instances.create(  # pylint: disable=no-member
        instance_config, wait=True
    )
    instance.start(timeout=10 * 60, wait=True)
    await wait_for(partial(_instance_running, instance))

    return instance


def _instance_running(instance: Instance) -> bool:
    """Check if the instance is running.

    Args:
        instance: The lxd instance.

    Returns:
        Whether the instance is running.
    """
    state: InstanceState = instance.state()
    if state.status != "Running":
        return False
    try:
        result = instance.execute(
            ["sudo", "--user", "ubuntu", "sudo", "systemctl", "is-active", "snapd.seeded.service"]
        )
    except BrokenPipeError:
        return False
    return result.exit_code == 0


@dataclasses.dataclass
class OpenStackConnectionParams:
    """Parameters for connecting to OpenStack instance.

    Attributes:
        connection: The openstack connection client to communicate with Openstack.
        server_name: Openstack server to find the valid connection from.
        network: The network to find valid connection from.
        ssh_key: The path to public ssh_key to create connection with.
    """

    connection: Connection
    server_name: str
    network: str
    ssh_key: Path


async def wait_for_valid_connection(
    connection_params: OpenStackConnectionParams,
    timeout: int = 30 * 60,
    dockerhub_mirror: urllib.parse.ParseResult | None = None,
) -> SSHConnection:
    """Wait for a valid SSH connection from Openstack server.

    Args:
        connection_params: Parameters for connecting to OpenStack instance.
        timeout: Number of seconds to wait before raising a timeout error.
        dockerhub_mirror: The DockerHub mirror URL.

    Raises:
        TimeoutError: If no valid connections were found.

    Returns:
        SSHConnection.
    """
    start_time = time.time()
    while time.time() - start_time <= timeout:
        server: Server | None = connection_params.connection.get_server(
            name_or_id=connection_params.server_name
        )
        if not server or not server.addresses:
            time.sleep(10)
            continue
        for address in server.addresses[connection_params.network]:
            ip = address["addr"]
            logger.info(
                "Trying SSH into %s using key: %s...",
                ip,
                str(connection_params.ssh_key.absolute()),
            )
            ssh_connection = SSHConnection(
                host=ip,
                user="ubuntu",
                connect_kwargs={"key_filename": str(connection_params.ssh_key.absolute())},
                connect_timeout=60 * 10,
            )
            try:
                result: Result = ssh_connection.run("echo 'hello world'")
                if result.ok:
                    _configure_dockerhub_mirror(
                        conn=ssh_connection, dockerhub_mirror=dockerhub_mirror
                    )
                    return ssh_connection
            except (NoValidConnectionsError, TimeoutError, SSHException) as exc:
                logger.warning("Connection not yet ready, %s.", str(exc))
        time.sleep(10)
    raise TimeoutError("No valid ssh connections found.")


def _snap_ready(conn: SSHConnection) -> bool:
    """Checks whether snapd is ready.

    Args:
        conn: The SSH connection instance.

    Returns:
        Whether snapd is ready.
    """
    command = "sudo systemctl is-active snapd.seeded.service"
    logger.info("Running command: %s", command)
    try:
        result: Result = conn.run(command)
        return result.ok
    except UnexpectedExit:
        return False


@tenacity.retry(
    wait=tenacity.wait_exponential(multiplier=2, min=10, max=60),
    stop=tenacity.stop_after_attempt(10),
)
def _configure_dockerhub_mirror(
    conn: SSHConnection, dockerhub_mirror: urllib.parse.ParseResult | None
):
    """Use dockerhub mirror if provided.

    Args:
        conn: The SSH connection instance.
        dockerhub_mirror: The DockerHub mirror URL.
    """
    if not dockerhub_mirror:
        return
    command = f'sudo mkdir -p /etc/docker/ && \
echo {{ \\"registry-mirrors\\": [\\"{dockerhub_mirror.geturl()}\\"]}} | sudo tee \
/etc/docker/daemon.json'
    logger.info("Running command: %s", command)
    result: Result = conn.run(command)
    assert result.ok, "Failed to setup DockerHub mirror"

    command = "sudo systemctl daemon-reload"
    result = conn.run(command)
    assert result.ok, "Failed to reload daemon"

    command = "sudo systemctl restart docker"
    result = conn.run(command)
    assert result.ok, "Failed to restart docker"


def format_dockerhub_mirror_microk8s_command(
    command: str, dockerhub_mirror: urllib.parse.ParseResult
) -> str:
    """Format dockerhub mirror for microk8s command.

    Args:
        command: The command to run.
        dockerhub_mirror: The DockerHub mirror URL.

    Returns:
        The formatted dockerhub mirror registry command for snap microk8s.
    """
    return command.format(
        registry_url=dockerhub_mirror.geturl(),
        hostname=dockerhub_mirror.hostname,
        port=dockerhub_mirror.port,
    )

def setup_aproxy(ssh_connection: SSHConnection, proxy: types.ProxyConfig):
    """Setup the aproxy in the openstack instance.
    
    Args:
        ssh_connection: SSH connection to the openstack instance.
        proxy: The proxy configuration.
    """
    ssh_connection.run(
        f"sudo snap set aproxy proxy={proxy.http} listen=:54969"
    )
    ssh_connection.run(
        """sudo tee /etc/nftables.conf > /dev/null << EOF
define default-ipv4 = $(ip route get $(ip route show 0.0.0.0/0 | grep -oP 'via \K\S+') | grep -oP 'src \K\S+')
table ip aproxy
flush table ip aproxy
table ip aproxy {
      set exclude {
          type ipv4_addr;
          flags interval; auto-merge;
          elements = { 127.0.0.0/8, {{ aproxy_exclude_ipv4_addresses }} }
      }
      chain prerouting {
              type nat hook prerouting priority dstnat; policy accept;
              ip daddr != @exclude tcp dport { {{ aproxy_redirect_ports }} } counter dnat to \$default-ipv4:54969
      }
      chain output {
              type nat hook output priority -100; policy accept;
              ip daddr != @exclude tcp dport { {{ aproxy_redirect_ports }} } counter dnat to \$default-ipv4:54969
      }
}
EOF
"""
    )
    ssh_connection.run(
        "sudo systemctl enable nftables.service"
    )
    ssh_connection.run(
        "sudo nft -f /etc/nftables.conf"
    )
    

def run_openstack_tests(ssh_connection: SSHConnection):
    """Run test commands on the openstack instance via ssh.

    Args:
        ssh_connection: The SSH connection instance to OpenStack test server.
    """
    for testcmd in commands.TEST_RUNNER_COMMANDS:
        logger.info("Running command: %s", testcmd.command)
        result: Result = ssh_connection.run(testcmd.command, env=testcmd.env)
        logger.info("Command output: %s %s %s", result.return_code, result.stdout, result.stderr)
        assert result.return_code == 0


# This is a simple interface for filtering out openstack objects.
class CreatedAtProtocol(Protocol):  # pylint: disable=too-few-public-methods
    """The interface for objects containing the created_at property.

    Attributes:
        created_at: The created_at timestamp of format YYYY-MM-DDTHH:MM:SSZ.
    """

    @property
    def created_at(self) -> str:
        """The object's creation timestamp."""


def is_greater_than_time(instance_to_check: CreatedAtProtocol, timestamp: datetime):
    """Return if object was created after given timestamp.

    Args:
        instance_to_check: The object to check for creation after timestamp.
        timestamp: The timestamp to check.

    Returns:
        Whether the object was created after given timestamp.
    """
    created_at = datetime.strptime(instance_to_check.created_at, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    return created_at > timestamp


# This is a simple interface for filtering out openstack objects.
class NameProtocol(Protocol):  # pylint: disable=too-few-public-methods
    """The interface for objects containing the name property.

    Attributes:
        name: The object name.
    """

    @property
    def name(self) -> str:
        """The object's name."""


def has_name(instance_to_check: NameProtocol, name: str):
    """Return if object has given name.

    Args:
        instance_to_check: The object to check for name equality.
        name: The name to check.

    Returns:
        Whether the object has given name.
    """
    return instance_to_check.name == name


def create_openstack_server(
    openstack_metadata: types.OpenstackMeta,
    server_name: str,
    image: OpenstackImage,
    security_group: SecurityGroup,
) -> Generator[Server, None, None]:
    """Create OpenStack server.

    Args:
        openstack_metadata: Wrapped openstack metadata.
        server_name: The server name to create as.
        image: Image used to create the server.
        security_group: Security group in which the instance belongs to.

    Yields:
        The Openstack server instance.
    """
    try:
        server: Server = openstack_metadata.connection.create_server(
            name=server_name,
            image=image,
            key_name=openstack_metadata.ssh_key.keypair.name,
            auto_ip=False,
            # these are pre-configured values on private endpoint.
            security_groups=[security_group.name],
            flavor=openstack_metadata.flavor,
            network=openstack_metadata.network,
            # hostname setting is required for microk8s testing
            userdata="""#!/bin/bash
hostnamectl set-hostname github-runner
""",
            # 2025/07/24 - This option is set to mitigate CVE-2024-6174
            config_drive=True,
            timeout=60 * 20,
            wait=True,
        )
        logger.info(
            "server console log output: %s",
            openstack_metadata.connection.get_server_console(server=server),
        )
        yield server
    except openstack.exceptions.SDKException:
        server = openstack_metadata.connection.get_server(name_or_id=server_name)
        logger.exception("Failed to create server, %s", dict(server))
    finally:
        openstack_metadata.connection.delete_server(server_name, wait=True)
