# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.


"""Module handling interactions with pipx."""

# Code is abstracting process interactions and is currently tested in integration tests.

import logging
import os
import subprocess  # nosec

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
    cmd = ["/usr/bin/pipx", *args]
    logger.info("Running pipx command: %s", cmd)
    logger.info(
        "Proxy env: HTTP_PROXY=%s, HTTPS_PROXY=%s, NO_PROXY=%s",
        os.environ.get("HTTP_PROXY", ""),
        os.environ.get("HTTPS_PROXY", ""),
        os.environ.get("NO_PROXY", ""),
    )
    try:
        subprocess.run(  # nosec: B603
            cmd,
            timeout=5 * 60,
            check=True,
            user=UBUNTU_USER,
            capture_output=True,
            text=True,
            env=os.environ,
        )
    except subprocess.CalledProcessError as exc:
        logger.error(
            "Pipx command failed, code: %s, stdout: %s, stderr: %s",
            exc.returncode,
            exc.stdout,
            exc.stderr,
        )
        raise PipXError from exc
    except subprocess.SubprocessError as exc:
        logger.error("Pipx subprocess error: %s", exc)
        raise PipXError from exc
