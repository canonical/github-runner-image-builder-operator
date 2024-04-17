# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for managing build intervals."""

import os
from pathlib import Path

from charms.operator_libs_linux.v1.systemd import service_restart

CRON_PATH = Path("/etc/cron.d")
BUILD_SCHEDULE_PATH = CRON_PATH / "build-runner-image"


def _should_setup(interval: int) -> bool:
    """Determine whether changes to cron should be applied.

    Args:
        interval: Incoming interval configuration to compare with current.

    Returns:
        True if interval has changed. False otherwise.
    """
    if not BUILD_SCHEDULE_PATH.exists():
        return True
    # See cron text in setup definition below
    current_interval = int(
        BUILD_SCHEDULE_PATH.read_text(encoding="utf-8").split()[1].split("/")[1]
    )
    return current_interval != interval


def setup(interval: int) -> None:
    """Configure cron job to periodically build image.

    Args:
        interval: The number of hours between periodic builds.
    """
    if not _should_setup(interval=interval):
        return

    if interval == 0:
        BUILD_SCHEDULE_PATH.unlink(missing_ok=True)
        service_restart("cron")
        return

    env = "JUJU_DISPATCH_PATH='hooks/cron' OPERATOR_DISPATCH=1"
    charm_exec_command = f"{os.getenv('JUJU_CHARM_DIR')}/dispatch"

    cron_text = f"0 */{interval} * * * ubuntu export {env}; {charm_exec_command}"
    BUILD_SCHEDULE_PATH.write_text(cron_text, encoding="utf-8")
    service_restart("cron")
