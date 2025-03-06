# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper utilities for integration tests."""

import dataclasses
import functools
import inspect
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable, ParamSpec, TypeVar, cast

from openstack.connection import Connection
from openstack.image.v2.image import Image

from tests.integration.types import ProxyConfig

logger = logging.getLogger(__name__)

CREATE_SERVER_TIMEOUT_IN_SECONDS = 15 * 60


async def wait_for_images(
    openstack_connection: Connection, dispatch_time: datetime, image_names: list[str]
):
    """Wait for images to be created.

    Args:
        openstack_connection: The openstack connection instance.
        dispatch_time: Time when the image build was dispatched.
        image_names: The image names to check for.
    """
    for image_name in image_names:
        await wait_for(
            functools.partial(
                image_created_from_dispatch,
                connection=openstack_connection,
                dispatch_time=dispatch_time,
                image_name=image_name,
            ),
            check_interval=30,
            timeout=60 * 50,
        )


def image_created_from_dispatch(
    image_name: str, connection: Connection, dispatch_time: datetime
) -> Image | None:
    """Return whether there is an image created after dispatch has been called.

    Args:
        image_name: The image name to check for.
        connection: The OpenStack connection instance.
        dispatch_time: Time when the image build was dispatched.

    Returns:
        Whether there exists an image that has been created after dispatch time.
    """
    images: list[Image] = connection.search_images(image_name)
    logger.info(
        "Image name: %s, Images: %s",
        image_name,
        tuple((image.id, image.name, image.created_at) for image in images),
    )
    # split logs, the image log is long and gets cut off.
    logger.info("Dispatch time: %s", dispatch_time)
    for image in images:
        if (
            datetime.strptime(image.created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            >= dispatch_time
        ):
            return image
    return None


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


@dataclasses.dataclass
class ImageTestMeta:
    """Testing configuration required for image VM testing.

    Attributes:
        proxy: The proxy to enable for testing.
        test_id: The unique testing ID.
    """

    proxy: ProxyConfig
    test_id: str
