# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for charm module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

from pathlib import Path
from unittest.mock import MagicMock

import ops
import pytest

import builder
import charm as charm_module
import image
import proxy
from charm import BUILD_SUCCESS_EVENT_NAME, GithubRunnerImageBuilderCharm, os
from state import CharmConfigInvalidError, CharmState


@pytest.fixture(name="charm", scope="module")
def charm_fixture():
    """Mock charm fixture w/ framework."""
    # this is required since current ops does not support charmcraft.yaml
    mock_framework = MagicMock(spec=ops.framework.Framework)
    mock_framework.meta.actions = ["build-image"]
    mock_framework.meta.relations = ["image"]
    charm = GithubRunnerImageBuilderCharm(mock_framework)
    return charm


def test__load_state_invalid_config(
    monkeypatch: pytest.MonkeyPatch, charm: GithubRunnerImageBuilderCharm
):
    """
    arrange: given a monkeypatched CharmState.from_charm that raises CharmConfigInvalidError.
    act: when _load_state is called.
    assert: charm is in blocked status.
    """
    monkeypatch.setattr(
        CharmState, "from_charm", MagicMock(side_effect=CharmConfigInvalidError("Invalid config"))
    )
    monkeypatch.setattr(image, "Observer", MagicMock())

    assert charm._load_state() is None
    assert charm.unit.status == ops.BlockedStatus("Invalid config")


@pytest.mark.parametrize(
    "hook",
    [
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
    monkeypatch.setattr(
        CharmState, "from_charm", MagicMock(side_effect=CharmConfigInvalidError("Invalid config"))
    )

    getattr(charm, hook)(MagicMock())

    assert charm.unit.status == ops.BlockedStatus("Invalid config")


def test__create_callback_script(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, charm: GithubRunnerImageBuilderCharm
):
    """
    arrange: given monkeypatched CALLBACK_SCRIPT_PATH.
    act: when _create_callback_script is called.
    assert: expected contents are written to path.
    """
    test_path = tmp_path / "test"
    charm.unit.name = (test_unit_name := "test_unit_name")
    charm.model.name = (test_model_name := "test_model_name")
    monkeypatch.setattr(charm_module, "CALLBACK_SCRIPT_PATH", test_path)
    monkeypatch.setattr(os, "getenv", MagicMock(return_value=(test_dir := "test_charm_dir")))

    charm._create_callback_script()

    contents = test_path.read_text(encoding="utf-8")
    assert (
        contents
        == f"""#! /bin/bash
OPENSTACK_IMAGE_ID="$1"

/usr/bin/juju-exec {test_unit_name} \
JUJU_DISPATCH_PATH="hooks/{BUILD_SUCCESS_EVENT_NAME}" \
JUJU_MODEL_NAME="{test_model_name}" \
JUJU_UNIT_NAME="{test_unit_name}" \
OPENSTACK_IMAGE_ID="$OPENSTACK_IMAGE_ID" \
{test_dir}/dispatch
"""
    )


def test__on_install_invalid_state(charm: GithubRunnerImageBuilderCharm):
    """
    arrange: given a monkeypatched _load_state internal method that returns false.
    act: when on_install is called.
    assert: the event is deferred.
    """
    original_load_state = charm._load_state
    charm._load_state = MagicMock(return_value=False)

    charm._on_install(event=(mock_event := MagicMock()))

    mock_event.defer.assert_called_once()
    charm._load_state = original_load_state


def test__on_install(monkeypatch: pytest.MonkeyPatch, charm: GithubRunnerImageBuilderCharm):
    """
    arrange: given a monekypatched builder.setup_builder function.
    act: when _on_install is called.
    assert: setup_builder is called.
    """
    monkeypatch.setattr(CharmState, "from_charm", MagicMock())
    monkeypatch.setattr(image, "Observer", MagicMock())
    monkeypatch.setattr(proxy, "setup", MagicMock())
    monkeypatch.setattr(proxy, "configure_aproxy", MagicMock())
    monkeypatch.setattr(builder, "setup_builder", (setup_mock := MagicMock()))
    monkeypatch.setattr(builder, "build_immediate", (run_mock := MagicMock()))
    charm._create_callback_script = (create_callback := MagicMock())

    charm._on_install(MagicMock())

    create_callback.assert_called_once()
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
    monkeypatch.setattr(CharmState, "from_charm", MagicMock())
    monkeypatch.setattr(
        image, "Observer", MagicMock(return_value=(image_observer_mock := MagicMock()))
    )
    monkeypatch.setattr(proxy, "configure_aproxy", MagicMock())
    monkeypatch.setattr(builder, "install_clouds_yaml", MagicMock())
    monkeypatch.setattr(builder, "configure_cron", MagicMock(return_value=configure_cron))
    monkeypatch.setattr(builder, "build_immediate", MagicMock())
    charm.image_observer = image_observer_mock

    charm._on_config_changed(MagicMock())

    assert charm.unit.status == ops.ActiveStatus()


def test__on_build_success_error(
    monkeypatch: pytest.MonkeyPatch, charm: GithubRunnerImageBuilderCharm
):
    """
    arrange: given a monkeypatched mock os.getenv function that returns no value.
    act: when _on_build_success is called.
    assert: the charm is in ActiveStatus with a message.
    """
    monkeypatch.setattr(os, "getenv", MagicMock(return_value=""))

    charm._on_build_success(MagicMock)

    assert isinstance(charm.unit.status, ops.ActiveStatus)
    assert "Failed to build image." in charm.unit.status.message


def test__on_build_success(monkeypatch: pytest.MonkeyPatch, charm: GithubRunnerImageBuilderCharm):
    """
    arrange: given a monkeypatched mock os.getenv function.
    act: when _on_build_success is called.
    assert: the charm is in active status.
    """
    monkeypatch.setattr(os, "getenv", MagicMock())

    charm._on_build_success(MagicMock)

    assert charm.unit.status == ops.ActiveStatus()
