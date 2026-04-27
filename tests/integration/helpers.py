# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper utilities for integration tests."""

import dataclasses
import functools
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypeVar

import jubilant
import tenacity
from openstack.connection import Connection
from openstack.image.v2.image import Image

from tests.integration.types import ProxyConfig

logger = logging.getLogger(__name__)

CREATE_SERVER_TIMEOUT_IN_SECONDS = 15 * 60

_JUJU_SSH_RETRY_ATTEMPTS = 5
_JUJU_SSH_RETRY_WAIT_SECONDS = 30


@tenacity.retry(
    retry=tenacity.retry_if_exception_type(jubilant.CLIError),
    wait=tenacity.wait_fixed(_JUJU_SSH_RETRY_WAIT_SECONDS),
    stop=tenacity.stop_after_attempt(_JUJU_SSH_RETRY_ATTEMPTS),
    before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def juju_ssh(juju: jubilant.Juju, unit_name: str, command: str) -> str:
    """Run a command over SSH on a Juju unit, retrying on transient failures.

    Args:
        juju: The jubilant Juju instance.
        unit_name: The name of the unit (e.g. ``myapp/0``).
        command: Shell command to execute on the unit.

    Returns:
        The standard output of the command.
    """
    return juju.ssh(unit_name, command)


def wait_for_images(
    openstack_connection: Connection, dispatch_time: datetime, image_names: list[str]
):
    """Wait for images to be created.

    Args:
        openstack_connection: The openstack connection instance.
        dispatch_time: Time when the image build was dispatched.
        image_names: The image names to check for.
    """
    for image_name in image_names:
        wait_for(
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


R = TypeVar("R")


def wait_for(
    func: Callable[[], R],
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
    while time.time() < deadline:
        if result := func():
            return result
        time.sleep(check_interval)

    # final check before raising TimeoutError.
    if result := func():
        return result
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
