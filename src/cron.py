# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for managing build intervals."""

import os
from pathlib import Path

import ops
from charms.operator_libs_linux.v1.systemd import service_restart


class CronEvent(ops.EventBase):
    """Represents a cron triggered event."""


class CronEvents(ops.CharmEvents):
    """Represents events triggered by cron.

    Attributes:
        trigger: Represents a cron trigger event.
    """

    trigger = ops.EventSource(CronEvent)


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


def setup(interval: int, model_name: str, unit_name: str) -> None:
    """Configure cron job to periodically build image.

    Args:
        interval: The number of hours between periodic builds.
        model_name: THe model in which the unit belongs to.
        unit_name: The unit name to setup the cron job for.
    """
    if not _should_setup(interval=interval):
        return

    if interval == 0:
        BUILD_SCHEDULE_PATH.unlink(missing_ok=True)
        service_restart("cron")
        return

    # Copy current execution env & overwrite dispatch hook path
    cur_env = {
        "JUJU_DISPATCH_PATH": "hooks/trigger",
        "JUJU_MODEL_NAME": model_name,
        "JUJU_UNIT_NAME": unit_name,
    }
    env = " ".join(f'{key}="{val}"' for (key, val) in cur_env.items())
    charm_dir = os.getenv("JUJU_CHARM_DIR")
    charm_exec_command = f"/usr/bin/juju-exec {unit_name} {env} {charm_dir}/dispatch"

    cron_text = f"0 */{interval} * * * root {charm_exec_command}\n"
    BUILD_SCHEDULE_PATH.write_text(cron_text, encoding="utf-8")
    service_restart("cron")
