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


def test__on_image_relation_joined_unit_data_not_ready(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    """
    arrange: given a monkeypatched OpenstackManager.get_latest_image_id that returns no image.
    act: when _on_image_relation_joined hook is fired.
    assert: image not ready warning is logged.
    """
    monkeypatch.setattr(state.BuilderRunConfig, "from_charm", MagicMock())
    monkeypatch.setattr(
        state.CloudsAuthConfig, "from_unit_relation_data", MagicMock(return_value=None)
    )

    observer = image.Observer(MagicMock())
    observer._on_image_relation_joined(MagicMock())

    assert all("Unit relation data not yet ready." in log for log in caplog.messages)


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
    monkeypatch.setattr(builder, "install_clouds_yaml", MagicMock(return_value=""))
    monkeypatch.setattr(image.builder, "get_latest_images", MagicMock(return_value=""))
    mock_event = MagicMock()
    mock_event.unit = MagicMock()
    mock_event.unit.name = (test_unit_name := "test-unit-name")

    observer = image.Observer(MagicMock())
    observer._on_image_relation_joined(mock_event)

    assert all(f"Image not yet ready for {test_unit_name}." in log for log in caplog.messages)


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
    monkeypatch.setattr(builder, "install_clouds_yaml", MagicMock())
    monkeypatch.setattr(builder, "get_latest_images", MagicMock(return_value="test-id"))

    image_observer.update_image_data = (update_relation_data_mock := MagicMock())
    image_observer._on_image_relation_joined(MagicMock())

    update_relation_data_mock.assert_called()


def test_update_image_data_no_unit_data(harness: Harness, image_observer: image.Observer):
    """
    arrange: given unit with no relation data populated yet.
    act: when update_relation_data is called.
    assert: the unit is skipped and no relation data update happens.
    """
    # ignore _on_image_relation_changed event handler
    harness.charm._on_image_relation_changed = lambda *args, **kwargs: ...
    relation_id = harness.add_relation(
        state.IMAGE_RELATION,
        remote_app="github-runner",
    )
    harness.add_relation_unit(relation_id=relation_id, remote_unit_name="github-runner/0")

    image_observer.update_image_data(
        cloud_images=[
            [
                builder.CloudImage(
                    arch=state.Arch.ARM64,
                    base=state.BaseImage.JAMMY,
                    cloud_id="test_test",
                    image_id="test",
                    juju="3.1/stable",
                    microk8s="",
                )
            ]
        ],
    )

    assert (
        harness.get_relation_data(
            relation_id=relation_id, app_or_unit=image_observer.model.unit.name
        )
        == {}
    )


def test_update_image_data(harness: Harness, image_observer: image.Observer):
    """
    arrange: given multiple relations.
    act: when _on_image_relation_joined hook is fired.
    assert: update_relation_data is called.
    """
    # ignore _on_image_relation_changed event handler
    harness.charm._on_image_relation_changed = lambda *args, **kwargs: ...
    first_relation_id = harness.add_relation(
        state.IMAGE_RELATION,
        remote_app="github-runner",
    )
    harness.add_relation_unit(relation_id=first_relation_id, remote_unit_name="github-runner/0")
    harness.update_relation_data(
        relation_id=first_relation_id,
        app_or_unit="github-runner/0",
        key_values={
            "auth_url": "test",
            "password": "test",
            "project_domain_name": "test",
            "project_name": "test",
            "user_domain_name": "test",
            "username": "test",
        },
    )
    harness.add_relation_unit(relation_id=first_relation_id, remote_unit_name="github-runner/1")
    harness.update_relation_data(
        relation_id=first_relation_id,
        app_or_unit="github-runner/1",
        key_values={
            "auth_url": "test",
            "password": "test",
            "project_domain_name": "test",
            "project_name": "test",
            "user_domain_name": "test",
            "username": "test",
        },
    )
    second_relation_id = harness.add_relation(
        state.IMAGE_RELATION,
        remote_app="github-runner-two",
    )
    harness.add_relation_unit(
        relation_id=second_relation_id, remote_unit_name="github-runner-two/0"
    )
    harness.update_relation_data(
        relation_id=second_relation_id,
        app_or_unit="github-runner-two/0",
        key_values={
            "auth_url": "test",
            "password": "test",
            "project_domain_name": "test",
            "project_name": "test",
            "user_domain_name": "test",
            "username": "test",
        },
    )
    harness.add_relation_unit(
        relation_id=second_relation_id, remote_unit_name="github-runner-two/1"
    )
    harness.update_relation_data(
        relation_id=second_relation_id,
        app_or_unit="github-runner-two/1",
        key_values={
            "auth_url": "test",
            "password": "test",
            "project_domain_name": "test",
            "project_name": "test",
            "user_domain_name": "test",
            "username": "test",
        },
    )

    image_observer.update_image_data(
        cloud_images=[
            [
                builder.CloudImage(
                    arch=state.Arch.ARM64,
                    base=state.BaseImage.JAMMY,
                    cloud_id="test_test",
                    image_id="test",
                    juju="3.1/stable",
                    microk8s="",
                )
            ]
        ],
    )

    assert harness.get_relation_data(
        relation_id=first_relation_id, app_or_unit=image_observer.model.unit.name
    ) == {
        "id": "test",
        "tags": "arm64,jammy,juju=3.1/stable",
        "images": '[{"id": "test", "tags": "arm64,jammy,juju=3.1/stable"}]',
    }
    assert harness.get_relation_data(
        relation_id=second_relation_id, app_or_unit=image_observer.model.unit.name
    ) == {
        "id": "test",
        "tags": "arm64,jammy,juju=3.1/stable",
        "images": '[{"id": "test", "tags": "arm64,jammy,juju=3.1/stable"}]',
    }


def test__build_cloud_to_images_map():
    """
    arrange: given cloud image list.
    act: when _build_cloud_to_images_map is called.
    assert: expected cloud id to image map is built.
    """
    cloud_images = [
        [
            image_1 := builder.CloudImage(
                arch=state.Arch.ARM64,
                base=state.BaseImage.JAMMY,
                cloud_id="cloud-1",
                image_id="image-1",
                juju="3.1/stable",
                microk8s="",
            ),
            image_2 := builder.CloudImage(
                arch=state.Arch.ARM64,
                base=state.BaseImage.JAMMY,
                cloud_id="cloud-1",
                image_id="image-2",
                juju="3.1/stable",
                microk8s="",
            ),
        ],
    ]

    assert image._build_cloud_to_images_map(cloud_images=cloud_images) == {
        "cloud-1": [image_1, image_2]
    }


def test__cloud_images_to_relation_data_no_images():
    """
    arrange: given no cloud images.
    act: when _cloud_images_to_relation_data is called.
    assert: ValueError is raised.
    """
    with pytest.raises(ValueError):
        image._cloud_images_to_relation_data(cloud_images=[])
