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


@pytest.mark.parametrize(
    "hook",
    [
        pytest.param("_on_config_changed", id="config_changed"),
        pytest.param("_on_run_action", id="run_action"),
        pytest.param("_on_run", id="run event"),
        pytest.param("_on_image_relation_changed", id="image_relation_changed"),
    ],
)
def test_block_on_image_relation_not_ready(charm: GithubRunnerImageBuilderCharm, hook: str):
    """
    arrange: given hooks that should not run build when image relation is not yet ready.
    act: when the hook is called.
    assert: the charm falls into BlockedStatus.
    """
    getattr(charm, hook)(MagicMock())

    assert charm.unit.status == ops.BlockedStatus(f"{state.IMAGE_RELATION} integration required.")


@pytest.mark.parametrize(
    "hook",
    [
        pytest.param("_on_install", id="_on_install"),
        pytest.param("_on_config_changed", id="_on_config_changed"),
        pytest.param("_on_run_action", id="_on_run_action"),
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
    monkeypatch.setattr(
        state.BuilderConfig,
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
    monkeypatch.setattr(state.BuilderConfig, "from_charm", MagicMock())
    monkeypatch.setattr(image, "Observer", MagicMock())
    monkeypatch.setattr(proxy, "setup", MagicMock())
    monkeypatch.setattr(builder, "initialize", (setup_mock := MagicMock()))

    charm._on_install(MagicMock())

    setup_mock.assert_called_once()
    assert charm.unit.status == ops.ActiveStatus("Waiting for first image.")


def test__on_image_relation_changed(
    monkeypatch: pytest.MonkeyPatch, charm: GithubRunnerImageBuilderCharm
):
    """
    arrange: given monkeypatched builder, openstack manager, image_observer.
    act: when _on_image_relation_changed is called.
    assert: charm is in active status.
    """
    monkeypatch.setattr(state.BuilderConfig, "from_charm", MagicMock())
    monkeypatch.setattr(proxy, "configure_aproxy", MagicMock())
    monkeypatch.setattr(builder, "install_clouds_yaml", MagicMock())
    monkeypatch.setattr(builder, "run", MagicMock())
    monkeypatch.setattr(builder, "upgrade_app", MagicMock())
    charm.image_observer = MagicMock()

    charm._on_image_relation_changed(MagicMock())

    assert charm.unit.status == ops.ActiveStatus()
