# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for image observer module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

from unittest.mock import MagicMock

import pytest
from ops.testing import Harness

import builder
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
    monkeypatch.setattr(state.CloudsAuthConfig, "from_unit_relation_data", MagicMock())
    monkeypatch.setattr(image.builder, "get_latest_image", MagicMock(return_value=""))

    observer = image.Observer(MagicMock())
    observer._on_image_relation_joined(MagicMock())

    assert all("Image not yet ready." in log for log in caplog.messages)


def test__on_image_relation_joined(
    monkeypatch: pytest.MonkeyPatch, image_observer: image.Observer
):
    """
    arrange: given a monkeypatched OpenstackManager.get_latest_image_id that returns an image ID.
    act: when _on_image_relation_joined hook is fired.
    assert: update_relation_data is called.
    """
    monkeypatch.setattr(state.BuilderRunConfig, "from_charm", MagicMock())
    monkeypatch.setattr(state.CloudsAuthConfig, "from_unit_relation_data", MagicMock())
    monkeypatch.setattr(image.builder, "get_latest_image", MagicMock(return_value="test-id"))

    image_observer.update_image_data = (update_relation_data_mock := MagicMock())
    image_observer._on_image_relation_joined(MagicMock())

    update_relation_data_mock.assert_called()


def test_init(harness: Harness, image_observer: image.Observer):
    """
    arrange: given a monkeypatched OpenstackManager.get_latest_image_id that returns an image ID.
    act: when _on_image_relation_joined hook is fired.
    assert: update_relation_data is called.
    """
    harness.charm._on_image_relation_changed = lambda *args, **kwargs: ...
    harness.add_relation(
        state.IMAGE_RELATION,
        remote_app="github-runner",
        unit_data={
            "auth_url": "test",
            "password": "test",
            "project_domain_name": "test",
            "project_name": "test",
            "user_domain_name": "test",
            "username": "test",
        },
    )

    image_observer.update_image_data(
        cloud_image_ids=[builder.CloudImage(cloud_id="test", image_id="test")],
        arch=state.Arch.ARM64,
        base=state.BaseImage.JAMMY,
    )
