#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration testing module."""

import contextlib
import json
import logging
from datetime import datetime, timezone

import jubilant
import pytest
from openstack.connection import Connection

from builder import CRON_BUILD_SCHEDULE_PATH
from state import BUILD_INTERVAL_CONFIG_NAME
from tests.integration.helpers import image_created_from_dispatch, wait_for_images

logger = logging.getLogger(__name__)


def test_image_relation(juju: jubilant.Juju, app: str, test_charm: str):
    """
    arrange: An active charm and a test charm that becomes active when valid relation data is set.
    act: When the relation is joined.
    assert: The test charm becomes active due to proper relation data.
    """
    juju.integrate(app, test_charm)
    juju.wait(lambda s: jubilant.all_active(s, app), timeout=60 * 60)


@pytest.mark.abort_on_fail
def test_cos_agent_relation(juju: jubilant.Juju, app: str):
    """
    arrange: An active charm.
    act: When the cos-agent relation is joined.
    assert: The test charm becomes active.
    """
    grafana_agent_name = f"grafana-agent-{app}"
    juju.deploy(
        "grafana-agent",
        grafana_agent_name,
        channel="1/edge",
        base="ubuntu@22.04",
    )
    juju.integrate(f"{app}:cos-agent", f"{grafana_agent_name}:cos-agent")
    juju.wait(lambda s: jubilant.all_active(s, app), timeout=30 * 60)


@pytest.mark.abort_on_fail
def test_build_image(
    openstack_connection: Connection,
    dispatch_time: datetime,
    image_names: list[str],
):
    """
    arrange: A deployed active charm.
    act: When openstack images are listed.
    assert: An image is built successfully.
    """
    wait_for_images(openstack_connection, dispatch_time, image_names)


# Ignore the "too many arguments" warning, as this is not significant for a test function where
# the arguments are fixtures and the function is not expected to be called directly.
@pytest.mark.abort_on_fail
def test_charm_another_app_does_not_rebuild_image(  # pylint: disable=R0913,R0914,R0917
    juju: jubilant.Juju,
    app: str,
    test_charm: str,
    test_charm_2: str,
    openstack_connection: Connection,
    image_names: list[str],
):
    """
    arrange: A test_charm that has already been integrated.
        And another test_charm_2 (with creds on the same cloud) that is not yet integrated.
    act: Integrate the test_charm_2 with the app.
    assert: No additional image is created but instead the already created ones are reused.
    """
    time_before_relation = datetime.now(tz=timezone.utc)

    juju.integrate(app, test_charm_2)
    juju.wait(lambda s: jubilant.all_active(s, test_charm_2), timeout=30 * 60)

    # Check that no new image is created
    for image_name in image_names:
        assert (
            image_created_from_dispatch(
                image_name=image_name,
                connection=openstack_connection,
                dispatch_time=time_before_relation,
            )
            is None
        )

    # Check that images in relation data is same for both test charms
    status = juju.status()
    image_builder_unit_name = next(iter(status.apps[app].units))
    test_charm_unit_name = next(iter(status.apps[test_charm].units))
    test_charm_unit_data_str = juju.cli("show-unit", test_charm_unit_name, "--format", "json")
    logger.info("Test charm unit data: %s", test_charm_unit_data_str)
    test_charm_unit_data = json.loads(test_charm_unit_data_str)

    test_charm_2_unit_name = next(iter(status.apps[test_charm_2].units))
    test_charm_2_unit_data_str = juju.cli("show-unit", test_charm_2_unit_name, "--format", "json")
    logger.info("Test charm 2 unit data: %s", test_charm_2_unit_data_str)
    test_charm_2_unit_data = json.loads(test_charm_2_unit_data_str)

    assert (
        test_charm_unit_data[test_charm_unit_name]["relation-info"][0]["related-units"][
            image_builder_unit_name
        ]["data"]["images"]
        == test_charm_2_unit_data[test_charm_2_unit_name]["relation-info"][0]["related-units"][
            image_builder_unit_name
        ]["data"]["images"]
    )


@pytest.mark.abort_on_fail
def test_periodic_rebuilt(
    juju: jubilant.Juju,
    app: str,
    app_config: dict,
    openstack_connection: Connection,
    image_names: list[str],
):
    """
    arrange: A deployed active charm.
    act: Modify the crontab to run every minute.
    assert: An image is built successfully.
    """
    juju.wait(lambda s: jubilant.all_active(s, app), timeout=30 * 60)

    dispatch_time = datetime.now(tz=timezone.utc)
    status = juju.status()
    unit_name = next(iter(status.apps[app].units))
    with _change_cronjob_to_minutes(
        juju, unit_name, current_hour_interval=app_config[BUILD_INTERVAL_CONFIG_NAME]
    ):
        wait_for_images(
            openstack_connection=openstack_connection,
            dispatch_time=dispatch_time,
            image_names=image_names,
        )


@contextlib.contextmanager
def _change_cronjob_to_minutes(juju: jubilant.Juju, unit_name: str, current_hour_interval: int):
    """Context manager to change the crontab to run every minute."""
    minute_interval = 1
    juju.ssh(
        unit_name,
        rf"sudo sed -i 's/0 \*\/{current_hour_interval}/\*\/{minute_interval} \*/g'  "
        f"{CRON_BUILD_SCHEDULE_PATH}",
    )
    cron_content = juju.ssh(unit_name, f"cat {CRON_BUILD_SCHEDULE_PATH}")
    logger.info("Cron file content: %s", cron_content)
    juju.ssh(unit_name, "sudo systemctl restart cron")

    try:
        yield
    finally:
        juju.ssh(
            unit_name,
            rf"sudo sed -i 's/\*\/{minute_interval} \*/0 \*\/{current_hour_interval}/g'  "
            f"{CRON_BUILD_SCHEDULE_PATH}",
        )
        cron_content = juju.ssh(unit_name, f"cat {CRON_BUILD_SCHEDULE_PATH}")
        logger.info("Cronfile content: %s", cron_content)
        juju.ssh(unit_name, "sudo systemctl restart cron")


@pytest.mark.abort_on_fail
def test_log_rotated(juju: jubilant.Juju, app: str):
    """
    arrange: A deployed active charm and manually write something to the log file.
    act: trigger logrotate manually
    assert: The log is rotated successfully.
    """
    juju.wait(lambda s: jubilant.all_agents_idle(s, app), timeout=30 * 60)
    status = juju.status()
    unit_name = next(iter(status.apps[app].units))
    test_log = "this log should be rotated"
    juju.ssh(
        unit_name,
        f"echo '{test_log}' | sudo tee -a /var/log/github-runner-image-builder/info.log",
    )

    # Test that the configuration is loaded successfully using --debug flag
    logrotate_debug_output = juju.ssh(
        unit_name, "sudo bash -c '/usr/sbin/logrotate /etc/logrotate.conf --debug 2>&1'"
    )
    assert (
        "rotating pattern: /var/log/github-runner-image-builder/info.log" in logrotate_debug_output
    )
    # Manually trigger logrotate using --force flag
    juju.ssh(unit_name, "sudo /usr/sbin/logrotate /etc/logrotate.conf --force")
    log_output = juju.ssh(unit_name, "sudo cat /var/log/github-runner-image-builder/info.log")
    assert test_log not in log_output
