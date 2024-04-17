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
from charm import GithubRunnerImageBuilderCharm, cron, openstack_manager
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
        pytest.param("_on_build_image_action", id="_on_build_image_action"),
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


def test__on_install(monkeypatch: pytest.MonkeyPatch, charm: GithubRunnerImageBuilderCharm):
    """
    arrange: given a monekypatched builder.setup_builder function.
    act: when _on_install is called.
    assert: setup_builder is called.
    """
    monkeypatch.setattr(image, "Observer", MagicMock())
    monkeypatch.setattr(builder, "setup_builder", (setup_mock := MagicMock()))

    charm._on_install(MagicMock())

    setup_mock.assert_called_once()


def test__on_config_changed(monkeypatch: pytest.MonkeyPatch, charm: GithubRunnerImageBuilderCharm):
    """
    arrange: given monkeypatched builder, openstack manager, image_observer.
    act: when _on_config_changed is called.
    assert: each module functions are called appropriately.
    """
    monkeypatch.setattr(CharmState, "from_charm", MagicMock())
    monkeypatch.setattr(
        image, "Observer", MagicMock(return_value=(image_observer_mock := MagicMock()))
    )
    monkeypatch.setattr(cron, "setup", (cron_mock := MagicMock()))
    charm.image_observer = image_observer_mock
    monkeypatch.setattr(builder, "build_image", (build_image_mock := MagicMock()))
    openstack_manager_contenxt_mock = MagicMock()
    openstack_manager_contenxt_mock.__enter__.return_value = (
        openstack_manager_mock := MagicMock()
    )
    monkeypatch.setattr(
        openstack_manager,
        "OpenstackManager",
        MagicMock(return_value=openstack_manager_contenxt_mock),
    )

    charm._on_config_changed(MagicMock())

    build_image_mock.assert_called_once()
    openstack_manager_mock.upload_image.assert_called_once()
    image_observer_mock.update_relation_data.assert_called_once()
    cron_mock.assert_called_once()


def test__on_build_image_action(
    monkeypatch: pytest.MonkeyPatch, charm: GithubRunnerImageBuilderCharm
):
    """
    arrange: given monkeypatched builder, openstack manager, image_observer.
    act: when _on_build_image_action is called.
    assert: each module functions are called appropriately.
    """
    monkeypatch.setattr(CharmState, "from_charm", MagicMock())
    monkeypatch.setattr(
        image, "Observer", MagicMock(return_value=(image_observer_mock := MagicMock()))
    )
    charm.image_observer = image_observer_mock
    monkeypatch.setattr(builder, "build_image", (build_image_mock := MagicMock()))
    openstack_manager_contenxt_mock = MagicMock()
    openstack_manager_contenxt_mock.__enter__.return_value = (
        openstack_manager_mock := MagicMock()
    )
    monkeypatch.setattr(
        openstack_manager,
        "OpenstackManager",
        MagicMock(return_value=openstack_manager_contenxt_mock),
    )

    charm._on_build_image_action(MagicMock())

    build_image_mock.assert_called_once()
    openstack_manager_mock.upload_image.assert_called_once()
    image_observer_mock.update_relation_data.assert_called_once()
