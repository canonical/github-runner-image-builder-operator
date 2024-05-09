# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper utilities for integration tests."""

import inspect
import logging
import time
from pathlib import Path
from typing import Awaitable, Callable, ParamSpec, TypeVar, cast

from fabric import Connection as SSHConnection
from fabric import Result
from openstack.compute.v2.server import Server
from openstack.connection import Connection
from paramiko.ssh_exception import NoValidConnectionsError

from tests.integration.types import ProxyConfig

logger = logging.getLogger(__name__)


def wait_for_valid_connection(
    connection: Connection,
    server_name: str,
    network: str,
    ssh_key: Path,
    timeout: int = 30 * 60,
    proxy: ProxyConfig | None = None,
) -> SSHConnection:
    """Wait for a valid SSH connection from Openstack server.

    Args:
        connection: The openstack connection client to communicate with Openstack.
        server_name: Openstack server to find the valid connection from.
        network: The network to find valid connection from.
        ssh_key: The path to public ssh_key to create connection with.
        timeout: Number of seconds to wait before raising a timeout error.
        proxy: The proxy to configure on host runner.

    Raises:
        TimeoutError: If no valid connections were found.

    Returns:
        SSHConnection.
    """
    start_time = time.time()
    while time.time() - start_time <= timeout:
        server: Server | None = connection.get_server(name_or_id=server_name)
        if not server or not server.addresses:
            time.sleep(10)
            continue
        for address in server.addresses[network]:
            ip = address["addr"]
            logger.info("Trying SSH into %s using key: %s...", ip, str(ssh_key.absolute()))
            ssh_connection = SSHConnection(
                host=ip,
                user="ubuntu",
                connect_kwargs={"key_filename": str(ssh_key.absolute())},
                connect_timeout=10,
            )
            try:
                if proxy and proxy.http:
                    # required to setup microk8s
                    no_proxy = ",".join(
                        [
                            proxy.no_proxy,
                            "10.0.0.0/8" "192.168.0.0/16",
                            "127.0.0.1",
                            "172.16.0.0/16",
                        ]
                    )
                    command = (
                        f"echo 'HTTP_PROXY={proxy.http}\nHTTPS_PROXY={proxy.https}\n"
                        f"NO_PROXY={no_proxy}\n"
                        f"http_proxy={proxy.http}\nhttps_proxy={proxy.https}\n"
                        f"no_proxy={no_proxy}\n' | sudo tee -a /etc/environment"
                    )
                else:
                    command = "echo 'hello world'"
                result: Result = ssh_connection.run(command)
                if result.ok:
                    return ssh_connection
            except NoValidConnectionsError as exc:
                logger.warn("Connection not yet ready, %s.", str(exc))
        time.sleep(10)
    raise TimeoutError("No valid ssh connections found.")


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
