# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for builder module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

from unittest.mock import MagicMock

import pytest
from openstack.connection import Connection

from github_runner_image_builder import store
from github_runner_image_builder.store import Image, OpenstackError, UploadImageError, openstack
from tests.unit.factories import MockOpenstackImageFactory


# Fixture docstrings do not need argument or return values.
@pytest.fixture(name="mock_connection")
def mock_connection_fixture(monkeypatch: pytest.MonkeyPatch) -> Connection:
    """Mock the openstack connection instance."""  # noqa: DCO020
    connection_mock = MagicMock()
    connection_context_mock = MagicMock(spec=Connection)
    connection_mock.__enter__.return_value = connection_context_mock
    monkeypatch.setattr(openstack, "connect", MagicMock(return_value=connection_mock))
    return connection_context_mock  # noqa: DCO030


def test_create_image_snapshot_error(mock_connection: MagicMock):
    """
    arrange: given mock connection that raises an error.
    act: when create_image_snapshot is called.
    assert: UploadImageError is raised.
    """
    mock_connection.create_image_snapshot.side_effect = (
        openstack.exceptions.OpenStackCloudException()
    )

    with pytest.raises(store.UploadImageError):
        store.create_snapshot(
            cloud_name=MagicMock(),
            image_name=MagicMock(),
            server=MagicMock(),
            keep_revisions=3,
        )


def test_create_image_snapshot(monkeypatch: pytest.MonkeyPatch, mock_connection: MagicMock):
    """
    arrange: given mock connection.
    act: when create_image_snapshot is called.
    assert: create_image_snapshot is called and prune image functions are called.
    """
    monkeypatch.setattr(store, "_prune_old_images", prune_images_mock := MagicMock())

    store.create_snapshot(
        cloud_name=MagicMock(),
        image_name=MagicMock(),
        server=MagicMock(),
        keep_revisions=3,
    )

    mock_connection.create_image_snapshot.assert_called()
    prune_images_mock.assert_called_once()


def test__get_sorted_images_by_created_at_error(mock_connection: MagicMock):
    """
    arrange: given a mocked openstack connection that returns images in non-sorted order.
    act: when _get_sorted_images_by_created_at is called.
    assert: the images are returned in sorted order by creation date.
    """
    mock_connection.search_images.side_effect = openstack.exceptions.OpenStackCloudException(
        "Network error"
    )

    with pytest.raises(OpenstackError) as err:
        store._get_sorted_images_by_created_at(connection=mock_connection, image_name=MagicMock)

    assert "Network error" in str(err.getrepr())


def test__get_sorted_images_by_created_at(mock_connection: MagicMock):
    """
    arrange: given a mocked openstack connection that returns images in non-sorted order.
    act: when _get_sorted_images_by_created_at is called.
    assert: the images are returned in sorted order by creation date.
    """
    mock_connection.search_images.return_value = [
        (first := MockOpenstackImageFactory(id="1", created_at="2024-01-01T00:00:00Z")),
        (third := MockOpenstackImageFactory(id="3", created_at="2024-03-03T00:00:00Z")),
        (second := MockOpenstackImageFactory(id="2", created_at="2024-02-02T00:00:00Z")),
    ]

    assert store._get_sorted_images_by_created_at(
        connection=mock_connection, image_name=MagicMock
    ) == [third, second, first]


def test__prune_old_images_error(mock_connection: MagicMock):
    """
    arrange: given a mocked delete function that raises an exception.
    act: when _prune_old_images is called.
    assert: failure to delete is logged.
    """
    mock_connection.search_images.return_value = [
        MockOpenstackImageFactory(id="1", created_at="2024-01-01T00:00:00Z"),
        MockOpenstackImageFactory(id="2", created_at="2024-02-02T00:00:00Z"),
    ]
    mock_connection.delete_image.side_effect = openstack.exceptions.OpenStackCloudException(
        "Delete error"
    )

    with pytest.raises(OpenstackError):
        store._prune_old_images(
            connection=mock_connection, image_name=MagicMock(), num_revisions=0
        )


def test__prune_old_images_fail(mock_connection: MagicMock):
    """
    arrange: given a mocked delete function that returns false.
    act: when _prune_old_images is called.
    assert: failure to delete is logged.
    """
    mock_connection.search_images.return_value = [
        MockOpenstackImageFactory(id="1", created_at="2024-01-01T00:00:00Z"),
        MockOpenstackImageFactory(id="2", created_at="2024-02-02T00:00:00Z"),
    ]
    mock_connection.delete_image.return_value = False

    with pytest.raises(OpenstackError):
        store._prune_old_images(
            connection=mock_connection, image_name=MagicMock(), num_revisions=0
        )


def test__prune_old_images(mock_connection: MagicMock):
    """
    arrange: given a mocked delete function that returns true.
    act: when _prune_old_images is called.
    assert: delete mock is called.
    """
    mock_connection.search_images.return_value = [
        MockOpenstackImageFactory(id="1", created_at="2024-01-01T00:00:00Z"),
        MockOpenstackImageFactory(id="2", created_at="2024-02-02T00:00:00Z"),
    ]
    mock_connection.delete_image.return_value = True

    store._prune_old_images(connection=mock_connection, image_name=MagicMock(), num_revisions=0)

    assert mock_connection.delete_image.call_count == 2


def test_upload_image_error(mock_connection: MagicMock):
    """
    arrange: given a mocked openstack create_image function that raises an exception.
    act: when upload_image is called.
    assert: UploadImageError is raised.
    """
    mock_connection.create_image.side_effect = openstack.exceptions.OpenStackCloudException(
        "Resource capacity exceeded."
    )

    with pytest.raises(UploadImageError) as exc:
        store.upload_image(
            arch=MagicMock(),
            cloud_name=MagicMock(),
            image_name=MagicMock(),
            image_path=MagicMock(),
            keep_revisions=MagicMock(),
        )

    assert "Resource capacity exceeded." in str(exc.getrepr())


def test_upload_image(mock_connection: MagicMock):
    """
    arrange: given a mocked openstack create_image function that raises an exception.
    act: when upload_image is called.
    assert: UploadImageError is raised.
    """
    mock_connection.create_image.return_value = (test_image := MockOpenstackImageFactory(id="1"))

    assert (
        store.upload_image(
            arch=MagicMock(),
            cloud_name=MagicMock(),
            image_name=MagicMock(),
            image_path=MagicMock(),
            keep_revisions=MagicMock(),
        )
        == test_image
    )


@pytest.mark.usefixtures("mock_connection")
@pytest.mark.parametrize(
    "images, expected_id",
    [
        pytest.param([], "", id="No images"),
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
    images: list[Image], expected_id: str | None, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: given a mocked _get_images_by_latest function that returns openstack images.
    act: when get_latest_image_id is called.
    assert: GetImageError is raised.
    """
    monkeypatch.setattr(
        store,
        "_get_sorted_images_by_created_at",
        MagicMock(return_value=images),
    )

    assert store.get_latest_build_id(cloud_name=MagicMock(), image_name=MagicMock()) == expected_id
