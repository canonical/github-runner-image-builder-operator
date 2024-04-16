# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for builder module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

from unittest.mock import MagicMock

import pytest

import openstack_manager
from openstack_manager import (
    GetImageError,
    Image,
    OpenstackConnectionError,
    OpenstackManager,
    UnauthorizedError,
    UploadImageError,
    openstack,
    yaml,
)
from tests.unit.factories import MockOpenstackImageFactory


@pytest.fixture(name="connection")
def mocked_openstack_connection_fixture():
    """Fixture for Openstack connection context manager mock instance."""
    connection_mock = MagicMock()
    return connection_mock


@pytest.fixture(name="manager")
def openstack_manager_mock_fixture(monkeypatch: pytest.MonkeyPatch, connection: MagicMock):
    """Fixture for OpenstackManager."""
    monkeypatch.setattr(openstack, "connect", MagicMock(return_value=connection))
    monkeypatch.setattr(openstack_manager, "CLOUDS_YAML_PATH", MagicMock())
    monkeypatch.setattr(yaml, "dump", MagicMock())
    return openstack_manager.OpenstackManager(cloud_config={"clouds": {"hello": "world"}})


def test_openstack_manager_context(monkeypatch: pytest.MonkeyPatch, connection: MagicMock):
    """
    arrange: given a monkeypatched openstack connection.
    act: when openstck manager context is entered and exited.
    assert: connection is closed.
    """
    monkeypatch.setattr(openstack, "connect", MagicMock(return_value=connection))
    monkeypatch.setattr(openstack_manager, "CLOUDS_YAML_PATH", MagicMock())
    monkeypatch.setattr(yaml, "dump", MagicMock())

    with openstack_manager.OpenstackManager(cloud_config={"clouds": {"hello": "world"}}):
        pass

    connection.close.assert_called_once()


def test___init__error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched openstack authorize function that raises an exception.
    act: when OpenstackManager is initialized.
    assert: UnauthorizedError is raised.
    """
    connect_mock = MagicMock()
    connect_mock.__enter__.return_value = (connection_mock := MagicMock())
    connection_mock.authorize.side_effect = openstack.exceptions.HttpException
    monkeypatch.setattr(openstack, "connect", MagicMock(return_value=connect_mock))
    monkeypatch.setattr(openstack_manager, "CLOUDS_YAML_PATH", MagicMock())
    monkeypatch.setattr(yaml, "dump", MagicMock())

    with pytest.raises(UnauthorizedError) as exc:
        openstack_manager.OpenstackManager(cloud_config={"clouds": {"hello": "world"}})

    assert "Unauthorized credentials." in str(exc.getrepr())


def test___init__multiple_clouds(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """
    arrange: given a monkeypatched openstack functions and multiple clouds input.
    act: when OpenstackManager is initialized.
    assert: Warning log is captured.
    """
    monkeypatch.setattr(openstack, "connect", MagicMock())
    monkeypatch.setattr(openstack_manager, "CLOUDS_YAML_PATH", MagicMock())
    monkeypatch.setattr(yaml, "dump", MagicMock())

    openstack_manager.OpenstackManager(
        cloud_config={"clouds": {"cloudone": "one", "cloudtwo": "two"}}
    )

    assert any("Multiple clouds defined" in log for log in caplog.messages)


def test__get_images_by_latest_error(connection: MagicMock, manager: OpenstackManager):
    """
    arrange: given a mocked openstack connection that returns images in non-sorted order.
    act: when _get_images_by_latest is called.
    assert: the images are returned in sorted order by creation date.
    """
    connection.search_images.side_effect = openstack.exceptions.OpenStackCloudException(
        "Network error"
    )

    with pytest.raises(OpenstackConnectionError) as err:
        manager._get_images_by_latest(image_name=MagicMock)

    assert "Network error" in str(err.getrepr())


def test__get_images_by_latest(connection: MagicMock, manager: OpenstackManager):
    """
    arrange: given a mocked openstack connection that returns images in non-sorted order.
    act: when _get_images_by_latest is called.
    assert: the images are returned in sorted order by creation date.
    """
    connection.search_images.return_value = [
        (first := MockOpenstackImageFactory(id="1", created_at="2024-01-01T00:00:00Z")),
        (third := MockOpenstackImageFactory(id="3", created_at="2024-03-03T00:00:00Z")),
        (second := MockOpenstackImageFactory(id="2", created_at="2024-02-02T00:00:00Z")),
    ]

    assert manager._get_images_by_latest(image_name=MagicMock) == [third, second, first]


def test__prune_old_images_error(
    caplog: pytest.LogCaptureFixture,
    connection: MagicMock,
    manager: OpenstackManager,
):
    """
    arrange: given a mocked delete function that raises an exception.
    act: when _prune_old_images is called.
    assert: failure to delete is logged.
    """
    connection.search_images.return_value = [
        MockOpenstackImageFactory(id="1", created_at="2024-01-01T00:00:00Z"),
        MockOpenstackImageFactory(id="2", created_at="2024-02-02T00:00:00Z"),
    ]
    connection.delete_image.side_effect = openstack.exceptions.OpenStackCloudException(
        "Delete error"
    )

    manager._prune_old_images(image_name=MagicMock(), num_revisions=0)

    assert all("Failed to prune old image" in log for log in caplog.messages)


def test__prune_old_images_fail(
    caplog: pytest.LogCaptureFixture, connection: MagicMock, manager: OpenstackManager
):
    """
    arrange: given a mocked delete function that returns false.
    act: when _prune_old_images is called.
    assert: failure to delete is logged.
    """
    connection.search_images.return_value = [
        MockOpenstackImageFactory(id="1", created_at="2024-01-01T00:00:00Z"),
        MockOpenstackImageFactory(id="2", created_at="2024-02-02T00:00:00Z"),
    ]
    connection.delete_image.return_value = False

    manager._prune_old_images(image_name=MagicMock(), num_revisions=0)

    assert all("Failed to delete old image" in log for log in caplog.messages)


def test__prune_old_images(connection: MagicMock, manager: OpenstackManager):
    """
    arrange: given a mocked delete function that returns true.
    act: when _prune_old_images is called.
    assert: delete mock is called.
    """
    connection.search_images.return_value = [
        MockOpenstackImageFactory(id="1", created_at="2024-01-01T00:00:00Z"),
        MockOpenstackImageFactory(id="2", created_at="2024-02-02T00:00:00Z"),
    ]
    connection.delete_image.return_value = True

    manager._prune_old_images(image_name=MagicMock(), num_revisions=0)

    assert connection.delete_image.call_count == 2


def test_upload_image_error(connection: MagicMock, manager: OpenstackManager):
    """
    arrange: given a mocked openstack create_image function that raises an exception.
    act: when upload_image is called.
    assert: UploadImageError is raised.
    """
    connection.create_image.side_effect = openstack.exceptions.OpenStackCloudException(
        "Resource capacity exceeded."
    )

    with pytest.raises(UploadImageError) as exc:
        manager.upload_image(config=MagicMock())

    assert "Resource capacity exceeded." in str(exc.getrepr())


def test_upload_image(connection: MagicMock, manager: OpenstackManager):
    """
    arrange: given a mocked openstack create_image function that raises an exception.
    act: when upload_image is called.
    assert: UploadImageError is raised.
    """
    connection.create_image.return_value = MockOpenstackImageFactory(id="1")

    assert manager.upload_image(config=MagicMock()) == "1"


def test_get_latest_image_id_error(manager: OpenstackManager):
    """
    arrange: given a mocked _get_images_by_latest function that raises an exception.
    act: when get_latest_image_id is called.
    assert: GetImageError is raised.
    """
    manager._get_images_by_latest = MagicMock(side_effect=OpenstackConnectionError("Unauthorized"))

    with pytest.raises(GetImageError) as exc:
        manager.get_latest_image_id(image_base=MagicMock())

    assert "Unauthorized" in str(exc.getrepr())


@pytest.mark.parametrize(
    "images, expected_id",
    [
        pytest.param([], None, id="No images"),
        pytest.param(
            [
                MockOpenstackImageFactory(id="1", created_at="2024-01-01T00:00:00Z"),
                MockOpenstackImageFactory(id="2", created_at="2024-02-02T00:00:00Z"),
            ],
            "1",
            id="Multiple images",
        ),
    ],
)
def test_get_latest_image_id(
    manager: OpenstackManager, images: list[Image], expected_id: str | None
):
    """
    arrange: given a mocked _get_images_by_latest function that returns openstack images.
    act: when get_latest_image_id is called.
    assert: GetImageError is raised.
    """
    manager._get_images_by_latest = MagicMock(return_value=images)

    assert manager.get_latest_image_id(image_base=MagicMock()) == expected_id
