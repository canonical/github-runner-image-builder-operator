# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.


"""Module handling interactions with pipx."""


# Code is abstracting process interactions and is currently tested in integration tests.

import logging
import subprocess

from exceptions import PipXError

UBUNTU_USER = "ubuntu"

logger = logging.getLogger(__name__)


def install(app_name: str) -> None:  # pragma: no cover
    # public interface should document exceptions
    """Install the application.

    Args:
        app_name: The name of the application to install.

    Raises:
        PipXError: If there was an error running the pipx command.  # noqa: DCO051
    """
    _pipx_cmd("install", app_name)


def uninstall(app_name: str) -> None:  # pragma: no cover
    """Uninstall the application.

    Args:
        app_name: The name of the application to uninstall.

    Raises:
        PipXError: If there was an error running the pipx command.      # noqa: DCO051
    """
    _pipx_cmd("uninstall", app_name)


def _pipx_cmd(*args: str) -> None:  # pragma: no cover
    """Install the application.

    Args:
        args: The arguments to pass to pipx CLI.

    Raises:
        PipXError: If there was an error running the pipx command
    """
    try:
        subprocess.run(  # nosec: B603
            [
                "/usr/bin/pipx",
                *args,
            ],
            timeout=5 * 60,
            check=True,
            user=UBUNTU_USER,
        )
    except subprocess.CalledProcessError as exc:
        logger.error(
            "Pipx command failed, code: %s, out: %s, err: %s",
            exc.returncode,
            exc.stdout,
            exc.stderr,
        )
        raise PipXError from exc
    except subprocess.SubprocessError as exc:
        raise PipXError from exc
