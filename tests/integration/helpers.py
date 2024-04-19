# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper utilities for integration tests."""

import inspect
import time
from pathlib import Path
from typing import Awaitable, Callable, ParamSpec, TypeVar, cast

from fabric import Connection as SSHConnection
from fabric import Result
from openstack.compute.v2.server import Server
from openstack.connection import Connection


def wait_for_valid_connection(
    connection: Connection, server_name: str, network: str, ssh_key: Path, timeout: int = 30 * 60
) -> SSHConnection:
    """Wait for a valid SSH connection from Openstack server.

    Args:
        connection: The openstack connection client to communicate with Openstack.
        server_name: Openstack server to find the valid connection from.
        network: The network to find valid connection from.
        ssh_key: The path to public ssh_key to create connection with.
        timeout: Number of seconds to wait before raising a timeout error.

    Raises:
        TimeoutError: If no valid connections were found.

    Returns:
        SSHConnection.
    """
    start_time = time.time()
    while time.time() - start_time <= timeout:
        server: Server = connection.get_server(name_or_id=server_name)
        for address in server.networks[network]:
            ip = address["addr"]
            ssh_connection = SSHConnection(
                host=ip,
                user="ubuntu",
                connect_kwargs={"key_filename": str(ssh_key.absolute())},
                connect_timeout=10,
            )
            result: Result = ssh_connection.run("echo 'hello world'")
            if result.ok:
                return ssh_connection
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
