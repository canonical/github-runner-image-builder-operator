# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for image observer module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

from unittest.mock import MagicMock

import pytest

import image
import state


@pytest.fixture(name="openstack_manager")
def openstack_manager_fixture(monkeypatch: pytest.MonkeyPatch):
    """Mock openstack manager."""
    manager = MagicMock()
    manager.__enter__.return_value = (instance := MagicMock())
    monkeypatch.setattr(image, "OpenstackManager", MagicMock(return_value=manager))
    return instance


def test__on_image_relation_joined_no_image(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    """
    arrange: given a monkeypatched OpenstackManager.get_latest_image_id that returns no image.
    act: when _on_image_relation_joined hook is fired.
    assert: image not ready warning is logged.
    """
    monkeypatch.setattr(state.BuilderRunConfig, "from_charm", MagicMock())
    monkeypatch.setattr(image.builder, "get_latest_image", MagicMock(return_value=""))

    observer = image.Observer(MagicMock())
    observer._on_image_relation_joined(MagicMock())

    assert all("Image not yet ready." in log for log in caplog.messages)


def test__on_image_relation_joined(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched OpenstackManager.get_latest_image_id that returns an image ID.
    act: when _on_image_relation_joined hook is fired.
    assert: update_relation_data is called.
    """
    monkeypatch.setattr(state.BuilderRunConfig, "from_charm", MagicMock())
    monkeypatch.setattr(image.builder, "get_latest_image", MagicMock(return_value="test-id"))

    observer = image.Observer(MagicMock())
    observer.update_image_id = (update_relation_data_mock := MagicMock())
    observer._on_image_relation_joined(MagicMock())

    update_relation_data_mock.assert_called()


def test_update_relation_data(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched OpenstackManager.get_latest_image_id that returns an image ID.
    act: when _on_image_relation_joined hook is fired.
    assert: update_relation_data is called.
    """
    monkeypatch.setattr(state.BuilderRunConfig, "from_charm", MagicMock())
    observer = image.Observer(MagicMock())
    # Harness doesn't understand latest charmcraft.yaml, so it can't be used here.
    observer.model.relations = {image.IMAGE_RELATION: [(relation := MagicMock())]}

    observer.update_image_id((test_id := "test-image-id"))

    relation.data[observer.model.unit].update.called_once_with(image.ImageRelationData(id=test_id))
