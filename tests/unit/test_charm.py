# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for charm module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

from unittest.mock import MagicMock

import ops
import pytest

import builder
import image
import proxy
import state
from charm import GithubRunnerImageBuilderCharm


@pytest.fixture(name="charm", scope="module")
def charm_fixture():
    """Mock charm fixture w/ framework."""
    # this is required since current ops does not support charmcraft.yaml
    mock_framework = MagicMock(spec=ops.framework.Framework)
    mock_framework.meta.actions = ["build-image"]
    mock_framework.meta.relations = ["image"]
    charm = GithubRunnerImageBuilderCharm(mock_framework)
    return charm


@pytest.mark.parametrize(
    "hook",
    [
        pytest.param("_on_install", id="_on_install"),
        pytest.param("_on_config_changed", id="_on_config_changed"),
    ],
)
def test_block_on_state_error(
    monkeypatch: pytest.MonkeyPatch, hook: str, charm: GithubRunnerImageBuilderCharm
):
    """
    arrange: given a monkeypatched CharmState.from_charm that raises CharmConfigInvalidError.
    act: when _load_state is called.
    assert: charm is in blocked status.
    """
    monkeypatch.setattr(image, "Observer", MagicMock())
    monkeypatch.setattr(state, "SUCCESS_CALLBACK_SCRIPT_PATH", MagicMock())
    monkeypatch.setattr(state, "FAILED_CALLBACK_SCRIPT_PATH", MagicMock())
    monkeypatch.setattr(
        state.BuilderInitConfig,
        "from_charm",
        MagicMock(side_effect=state.CharmConfigInvalidError("Invalid config")),
    )

    getattr(charm, hook)(MagicMock())

    assert charm.unit.status == ops.BlockedStatus("Invalid config")


def test__on_install(monkeypatch: pytest.MonkeyPatch, charm: GithubRunnerImageBuilderCharm):
    """
    arrange: given a monekypatched builder.setup_builder function.
    act: when _on_install is called.
    assert: setup_builder is called.
    """
    monkeypatch.setattr(state.BuilderInitConfig, "from_charm", MagicMock())
    monkeypatch.setattr(image, "Observer", MagicMock())
    monkeypatch.setattr(proxy, "setup", MagicMock())
    monkeypatch.setattr(proxy, "configure_aproxy", MagicMock())
    monkeypatch.setattr(builder, "initialize", (setup_mock := MagicMock()))
    monkeypatch.setattr(builder, "run", (run_mock := MagicMock()))
    charm._create_success_callback_script = (create_callback := MagicMock())
    charm._create_failed_callback_script = (failed_callback := MagicMock())

    charm._on_install(MagicMock())

    create_callback.assert_called_once()
    failed_callback.assert_called_once()
    setup_mock.assert_called_once()
    run_mock.assert_called_once()
    assert charm.unit.status == ops.ActiveStatus("Waiting for first image.")


@pytest.mark.parametrize(
    "configure_cron",
    [
        pytest.param(False, id="No reconfiguration"),
        pytest.param(True, id="Reconfigure"),
    ],
)
def test__on_config_changed(
    monkeypatch: pytest.MonkeyPatch, charm: GithubRunnerImageBuilderCharm, configure_cron: bool
):
    """
    arrange: given monkeypatched builder, openstack manager, image_observer.
    act: when _on_config_changed is called.
    assert: charm is in active status.
    """
    monkeypatch.setattr(state.BuilderInitConfig, "from_charm", MagicMock())
    monkeypatch.setattr(
        image, "Observer", MagicMock(return_value=(image_observer_mock := MagicMock()))
    )
    monkeypatch.setattr(proxy, "configure_aproxy", MagicMock())
    monkeypatch.setattr(builder, "install_clouds_yaml", MagicMock())
    monkeypatch.setattr(builder, "configure_cron", MagicMock(return_value=configure_cron))
    monkeypatch.setattr(builder, "run", MagicMock())
    charm.image_observer = image_observer_mock

    charm._on_config_changed(MagicMock())

    assert charm.unit.status == ops.ActiveStatus()
