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
from charm import GithubRunnerImageBuilderCharm, os
from state import CharmConfigInvalidError, CharmState


@pytest.fixture(name="resurrect", scope="module")
def resurrect_fixture():
    """Mock resurrect observer."""
    return MagicMock()


@pytest.fixture(name="charm", scope="module")
def charm_fixture(resurrect: MagicMock):
    """Mock charm fixture w/ framework."""
    # this is required since current ops does not support charmcraft.yaml
    mock_framework = MagicMock(spec=ops.framework.Framework)
    mock_framework.meta.actions = ["build-image"]
    mock_framework.meta.relations = ["image"]
    charm = GithubRunnerImageBuilderCharm(mock_framework)
    charm.resurrect = resurrect
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

    charm._on_install(MagicMock())

    setup_mock.assert_called_once()


def test__on_config_changed(monkeypatch: pytest.MonkeyPatch, charm: GithubRunnerImageBuilderCharm):
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
    monkeypatch.setattr(builder, "install_cron", MagicMock())
    charm.image_observer = image_observer_mock

    charm._on_config_changed(MagicMock())

    assert charm.unit.status == ops.ActiveStatus()


def test__on_build_success_error(
    monkeypatch: pytest.MonkeyPatch, charm: GithubRunnerImageBuilderCharm
):
    """
    arrange: given a monkeypatched mock os.getenv function that returns no value.
    act: when _on_build_success is called.
    assert: the charm raises an error.
    """
    monkeypatch.setattr(os, "getenv", MagicMock(return_value=""))

    with pytest.raises(ValueError):
        charm._on_build_success(MagicMock)


def test__on_build_success(monkeypatch: pytest.MonkeyPatch, charm: GithubRunnerImageBuilderCharm):
    """
    arrange: given a monkeypatched mock os.getenv function.
    act: when _on_build_success is called.
    assert: the charm is in active status.
    """
    monkeypatch.setattr(os, "getenv", MagicMock())

    charm._on_build_success(MagicMock)

    assert charm.unit.status == ops.ActiveStatus()
