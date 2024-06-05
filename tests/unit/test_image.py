# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for image observer module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

from unittest.mock import MagicMock

import ops
import pytest

import image
from image import (
    IMAGE_RELATION,
    BuilderSetupConfig,
    CharmConfigInvalidError,
    ImageRelationData,
    Observer,
)


@pytest.fixture(name="openstack_manager")
def openstack_manager_fixture(monkeypatch: pytest.MonkeyPatch):
    """Mock openstack manager."""
    manager = MagicMock()
    manager.__enter__.return_value = (instance := MagicMock())
    monkeypatch.setattr(image, "OpenstackManager", MagicMock(return_value=manager))
    return instance


def test__load_state_invalid_config(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched CharmState.from_charm that raises CharmConfigInvalidError.
    act: when _load_state is called.
    assert: charm is in blocked status.
    """
    monkeypatch.setattr(
        BuilderSetupConfig,
        "from_charm",
        MagicMock(side_effect=CharmConfigInvalidError("Invalid config")),
    )

    observer = Observer(MagicMock())

    assert observer._load_state() is None
    assert observer.charm.unit.status == ops.BlockedStatus("Invalid config")


@pytest.mark.parametrize(
    "hook", [pytest.param("_on_image_relation_joined", id="_on_image_relation_joined")]
)
def test_block_on_state_error(monkeypatch: pytest.MonkeyPatch, hook: str):
    """
    arrange: given a monkeypatched CharmState.from_charm that raises CharmConfigInvalidError.
    act: when _load_state is called.
    assert: charm is in blocked status.
    """
    monkeypatch.setattr(
        BuilderSetupConfig,
        "from_charm",
        MagicMock(side_effect=CharmConfigInvalidError("Invalid config")),
    )
    observer = Observer(MagicMock())

    getattr(observer, hook)(MagicMock())

    assert observer.charm.unit.status == ops.BlockedStatus("Invalid config")


def test__on_image_relation_joined_no_image(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    """
    arrange: given a monkeypatched OpenstackManager.get_latest_image_id that returns no image.
    act: when _on_image_relation_joined hook is fired.
    assert: image not ready warning is logged.
    """
    monkeypatch.setattr(BuilderSetupConfig, "from_charm", MagicMock())
    monkeypatch.setattr(image.builder, "get_latest_image", MagicMock(return_value=""))

    observer = Observer(MagicMock())
    observer._on_image_relation_joined(MagicMock())

    assert all("Image not yet ready." in log for log in caplog.messages)


def test__on_image_relation_joined(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched OpenstackManager.get_latest_image_id that returns an image ID.
    act: when _on_image_relation_joined hook is fired.
    assert: update_relation_data is called.
    """
    monkeypatch.setattr(BuilderSetupConfig, "from_charm", MagicMock())
    monkeypatch.setattr(image.builder, "get_latest_image", MagicMock(return_value="test-id"))

    observer = Observer(MagicMock())
    observer.update_image_id = (update_relation_data_mock := MagicMock())
    observer._on_image_relation_joined(MagicMock())

    update_relation_data_mock.assert_called()


def test_update_relation_data(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched OpenstackManager.get_latest_image_id that returns an image ID.
    act: when _on_image_relation_joined hook is fired.
    assert: update_relation_data is called.
    """
    monkeypatch.setattr(BuilderSetupConfig, "from_charm", MagicMock())
    observer = Observer(MagicMock())
    # Harness doesn't understand latest charmcraft.yaml, so it can't be used here.
    observer.model.relations = {IMAGE_RELATION: [(relation := MagicMock())]}

    observer.update_image_id((test_id := "test-image-id"))

    relation.data[observer.model.unit].update.called_once_with(ImageRelationData(id=test_id))
