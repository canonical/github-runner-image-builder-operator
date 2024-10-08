# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper utilities for integration tests."""

import dataclasses
import inspect
import logging
import time
import urllib
from pathlib import Path
from typing import Awaitable, Callable, ParamSpec, TypeVar, cast

from fabric import Connection as SSHConnection
from fabric import Result
from openstack.compute.v2.server import Server
from openstack.connection import Connection
from paramiko.ssh_exception import NoValidConnectionsError, SSHException

from tests.integration.types import ProxyConfig

logger = logging.getLogger(__name__)


def _install_proxy(conn: SSHConnection, proxy: ProxyConfig | None = None):
    """Run commands to install proxy.

    Args:
        conn: The SSH connection instance.
        proxy: The proxy to apply if available.
    """
    if not proxy or not proxy.http:
        return
    command = "sudo snap install aproxy --edge"
    logger.info("Running command: %s", command)
    result: Result = conn.run(command)
    assert result.ok, "Failed to install aproxy"

    proxy_str = proxy.http.replace("http://", "").replace("https://", "")
    command = f"sudo snap set aproxy proxy={proxy_str}"
    logger.info("Running command: %s", command)
    result = conn.run(command)
    assert result.ok, "Failed to setup aproxy"

    # ignore line too long since it is better read without line breaks
    command = """/usr/bin/sudo nft -f - << EOF
define default-ip = $(ip route get $(ip route show 0.0.0.0/0 | grep -oP 'via \\K\\S+') | grep -oP 'src \\K\\S+')
define private-ips = { 10.0.0.0/8, 127.0.0.1/8, 172.16.0.0/12, 192.168.0.0/16 }
table ip aproxy
flush table ip aproxy
table ip aproxy {
    chain prerouting {
            type nat hook prerouting priority dstnat; policy accept;
            ip daddr != \\$private-ips tcp dport { 80, 443 } counter dnat to \\$default-ip:8443
    }

    chain output {
            type nat hook output priority -100; policy accept;
            ip daddr != \\$private-ips tcp dport { 80, 443 } counter dnat to \\$default-ip:8443
    }
}
EOF"""  # noqa: E501
    logger.info("Running command: %s", command)
    result = conn.run(command)
    assert result.ok, "Failed to configure iptable rules"

    command = "sudo snap services aproxy"
    logger.info("Running command: %s", command)
    result = conn.run(command)
    assert result.ok, "Failed to check aproxy status"


def _configure_dockerhub_mirror(conn: SSHConnection, dockerhub_mirror: str | None):
    """Use dockerhub mirror if provided.

    Args:
        conn: The SSH connection instance.
        dockerhub_mirror: The DockerHub mirror URL.
    """
    if not dockerhub_mirror:
        return
    command = "sudo systemctl status docker --no-pager"
    logger.info("Running command: %s", command)
    result: Result = conn.run(command)
    assert result.ok, "Failed to show docker status"

    command = f"""sudo mkdir -p /etc/docker/ && \
echo '{{ "registry-mirrors": ["{dockerhub_mirror}"] }}' | \
sudo tee /etc/docker/daemon.json"""
    logger.info("Running command: %s", command)
    result = conn.run(command)
    assert result.ok, "Failed to setup DockerHub mirror"

    command = "sudo systemctl daemon-reload"
    logger.info("Running command: %s", command)
    result = conn.run(command)
    assert result.ok, "Failed to reload daemon"

    command = "sudo systemctl restart docker"
    logger.info("Running command: %s", command)
    result = conn.run(command)
    assert result.ok, "Failed to restart docker"


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


def wait_for_valid_connection(
    connection_params: OpenStackConnectionParams,
    timeout: int = 30 * 60,
    proxy: ProxyConfig | None = None,
    dockerhub_mirror: str | None = None,
) -> SSHConnection:
    """Wait for a valid SSH connection from Openstack server.

    Args:
        connection_params: Parameters for connecting to OpenStack instance.
        timeout: Number of seconds to wait before raising a timeout error.
        proxy: The proxy to configure on host runner.
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
                    _install_proxy(conn=ssh_connection, proxy=proxy)
                    _configure_dockerhub_mirror(
                        conn=ssh_connection, dockerhub_mirror=dockerhub_mirror
                    )
                    return ssh_connection
            except (NoValidConnectionsError, TimeoutError, SSHException) as exc:
                logger.warning("Connection not yet ready, %s.", str(exc))
        time.sleep(10)
    raise TimeoutError("No valid ssh connections found.")


def format_dockerhub_mirror_microk8s_command(command: str, dockerhub_mirror: str) -> str:
    """Format dockerhub mirror for microk8s command.

    Args:
        command: The command to run.
        dockerhub_mirror: The DockerHub mirror URL.

    Returns:
        The formatted dockerhub mirror registry command for snap microk8s.
    """
    url = urllib.parse.urlparse(dockerhub_mirror)
    return command.format(registry_url=url.geturl(), hostname=url.hostname, port=url.port)


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
