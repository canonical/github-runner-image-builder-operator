# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for builder module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

from unittest.mock import MagicMock, call

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
    mock_connection.image.images.side_effect = openstack.exceptions.OpenStackCloudException(
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
    mock_connection.image.images.return_value = [
        (first := MockOpenstackImageFactory(id="1", created_at="2024-01-01T00:00:00Z")),
        (third := MockOpenstackImageFactory(id="3", created_at="2024-03-03T00:00:00Z")),
        (second := MockOpenstackImageFactory(id="2", created_at="2024-02-02T00:00:00Z")),
    ]

    assert store._get_sorted_images_by_created_at(
        connection=mock_connection, image_name=MagicMock
    ) == [third, second, first]


def test_get_latest_build_id_any_status(mock_connection: MagicMock):
    """
    arrange: given a mocked openstack connection returning images via image proxy.
    act: when get_latest_build_id is called with active_only=False.
    assert: images under both the final and the temporary name are considered.
    """
    mock_connection.image = MagicMock()
    first = MockOpenstackImageFactory(id="1", created_at="2024-01-01T00:00:00Z")
    third = MockOpenstackImageFactory(id="3", created_at="2024-03-03T00:00:00Z")
    second = MockOpenstackImageFactory(id="2", created_at="2024-02-02T00:00:00Z")
    in_progress = MockOpenstackImageFactory(
        id="4", created_at="2024-04-04T00:00:00Z", status="saving"
    )
    mock_connection.image.images.side_effect = [
        iter([first, third, second]),
        iter([in_progress]),
    ]

    result = store.get_latest_build_id(
        cloud_name=MagicMock(), image_name="test-image", active_only=False
    )

    assert mock_connection.image.images.call_args_list == [
        call(name="test-image"),
        call(name=f"test-image{store.TMP_IMAGE_NAME_SUFFIX}"),
    ]
    assert result == "4"


def test_get_latest_build_id_active_only_ignores_tmp(mock_connection: MagicMock):
    """
    arrange: given an in-progress upload that is newer than the latest active image.
    act: when get_latest_build_id is called with the default active_only.
    assert: only the active image is returned and the temporary name is not queried.
    """
    mock_connection.image = MagicMock()
    active = MockOpenstackImageFactory(id="1", created_at="2024-01-01T00:00:00Z")
    saving = MockOpenstackImageFactory(id="2", created_at="2024-04-04T00:00:00Z", status="saving")
    mock_connection.image.images.side_effect = [iter([active, saving])]

    result = store.get_latest_build_id(cloud_name=MagicMock(), image_name="test-image")

    assert mock_connection.image.images.call_args_list == [call(name="test-image")]
    assert result == "1"


def test__get_sorted_images_by_created_at_any_status_error(mock_connection: MagicMock):
    """
    arrange: given a mocked openstack connection that raises on image proxy call.
    act: when _get_sorted_images_by_created_at is called with active_only=False.
    assert: OpenstackError is raised.
    """
    mock_connection.image = MagicMock()
    mock_connection.image.images.side_effect = openstack.exceptions.OpenStackCloudException(
        "Network error"
    )

    with pytest.raises(OpenstackError):
        store._get_sorted_images_by_created_at(
            connection=mock_connection, image_name=MagicMock, active_only=False
        )


def test__prune_old_images_error(mock_connection: MagicMock):
    """
    arrange: given a mocked delete function that raises an exception.
    act: when _prune_old_images is called.
    assert: failure to delete is logged.
    """
    mock_connection.image.images.return_value = [
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
    mock_connection.image.images.return_value = [
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
    mock_connection.image.images.return_value = [
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
    arrange: given a mocked openstack create_image function that uploads successfully.
    act: when upload_image is called.
    assert: the image is uploaded under a temporary name and the renamed image is returned.
    """
    mock_connection.image.images.return_value = []
    mock_connection.create_image.return_value = MockOpenstackImageFactory(id="1")
    mock_connection.image.update_image.return_value = (
        renamed_image := MockOpenstackImageFactory(id="1")
    )

    assert (
        store.upload_image(
            arch=MagicMock(),
            cloud_name=MagicMock(),
            image_name="test-image",
            image_path=MagicMock(),
            keep_revisions=MagicMock(),
        )
        == renamed_image
    )
    assert (
        mock_connection.create_image.call_args.kwargs["name"]
        == f"test-image{store.TMP_IMAGE_NAME_SUFFIX}"
    )
    assert mock_connection.create_image.call_args.kwargs["validate_checksum"] is True
    assert mock_connection.image.update_image.call_args.kwargs["name"] == "test-image"


def test_upload_image_deletes_leftover_tmp_image(mock_connection: MagicMock):
    """
    arrange: given a leftover temporary image from a previously interrupted upload.
    act: when upload_image is called.
    assert: the leftover image is deleted before the upload starts.
    """
    mock_connection.image.images.side_effect = [[MockOpenstackImageFactory(id="stale")], [], []]
    mock_connection.create_image.return_value = MockOpenstackImageFactory(id="1")
    mock_connection.image.update_image.return_value = MockOpenstackImageFactory(id="1")

    store.upload_image(
        arch=MagicMock(),
        cloud_name=MagicMock(),
        image_name="test-image",
        image_path=MagicMock(),
        keep_revisions=MagicMock(),
    )

    assert (
        mock_connection.image.images.call_args_list[0].kwargs["name"]
        == f"test-image{store.TMP_IMAGE_NAME_SUFFIX}"
    )
    mock_connection.delete_image.assert_any_call("stale", wait=True)


def test_upload_image_non_sha256_multihash(mock_connection: MagicMock):
    """
    arrange: given a cloud whose Glance computes the multihash with an algorithm other than sha256.
    act: when upload_image is called.
    assert: the image is accepted based on the md5 checksum alone.
    """
    mock_connection.image.images.return_value = []
    mock_connection.create_image.return_value = MockOpenstackImageFactory(
        id="1", hash_algo="sha512", hash_value="a-sha512-digest"
    )
    mock_connection.image.update_image.return_value = MockOpenstackImageFactory(id="1")

    store.upload_image(
        arch=MagicMock(),
        cloud_name=MagicMock(),
        image_name="test-image",
        image_path=MagicMock(),
        keep_revisions=MagicMock(),
    )

    mock_connection.image.update_image.assert_called_once()


def test_upload_image_checksum_mismatch_error(mock_connection: MagicMock):
    """
    arrange: given an uploaded image whose Glance hashes differ from the local ones.
    act: when upload_image is called.
    assert: UploadImageError is raised and the image is not renamed.
    """
    mock_connection.image.images.return_value = []
    mock_connection.create_image.return_value = MockOpenstackImageFactory(
        id="1", checksum="corrupted-md5"
    )

    with pytest.raises(UploadImageError) as exc:
        store.upload_image(
            arch=MagicMock(),
            cloud_name=MagicMock(),
            image_name="test-image",
            image_path=MagicMock(),
            keep_revisions=MagicMock(),
        )

    assert "Checksum mismatch" in str(exc.getrepr())
    mock_connection.image.update_image.assert_not_called()


def test_upload_image_sha256_mismatch_error(mock_connection: MagicMock):
    """
    arrange: given an uploaded image whose Glance sha256 differs from the local one.
    act: when upload_image is called.
    assert: UploadImageError is raised and the image is not renamed.
    """
    mock_connection.image.images.return_value = []
    mock_connection.create_image.return_value = MockOpenstackImageFactory(
        id="1", hash_algo="sha256", hash_value="corrupted-sha256"
    )

    with pytest.raises(UploadImageError) as exc:
        store.upload_image(
            arch=MagicMock(),
            cloud_name=MagicMock(),
            image_name="test-image",
            image_path=MagicMock(),
            keep_revisions=MagicMock(),
        )

    assert "sha256: corrupted-sha256 != test-sha256" in str(exc.getrepr())
    mock_connection.image.update_image.assert_not_called()


def test_upload_image_missing_checksum_error(mock_connection: MagicMock):
    """
    arrange: given an uploaded image without the locally computed hashes.
    act: when upload_image is called.
    assert: UploadImageError is raised and the image is not renamed.
    """
    mock_connection.image.images.return_value = []
    mock_connection.create_image.return_value = MockOpenstackImageFactory(id="1", properties={})

    with pytest.raises(UploadImageError) as exc:
        store.upload_image(
            arch=MagicMock(),
            cloud_name=MagicMock(),
            image_name="test-image",
            image_path=MagicMock(),
            keep_revisions=MagicMock(),
        )

    assert "missing the locally computed hashes" in str(exc.getrepr())
    mock_connection.image.update_image.assert_not_called()


def test_upload_image_deletes_tmp_image_on_error(mock_connection: MagicMock):
    """
    arrange: given an uploaded image that fails the checksum validation.
    act: when upload_image is called.
    assert: the temporary image is deleted.
    """
    mock_connection.image.images.side_effect = [
        [],
        [MockOpenstackImageFactory(id="1", name="test-image-tmp")],
    ]
    mock_connection.create_image.return_value = MockOpenstackImageFactory(id="1", properties={})

    with pytest.raises(UploadImageError):
        store.upload_image(
            arch=MagicMock(),
            cloud_name=MagicMock(),
            image_name="test-image",
            image_path=MagicMock(),
            keep_revisions=MagicMock(),
        )

    mock_connection.delete_image.assert_called_once_with("1", wait=True)


def test_upload_image_tmp_image_cleanup_error(mock_connection: MagicMock):
    """
    arrange: given a failed upload whose temporary image cannot be deleted.
    act: when upload_image is called.
    assert: the original error is raised instead of the cleanup error.
    """
    mock_connection.image.images.side_effect = [
        [],
        [MockOpenstackImageFactory(id="1", name="test-image-tmp")],
    ]
    mock_connection.create_image.return_value = MockOpenstackImageFactory(id="1", properties={})
    mock_connection.delete_image.side_effect = openstack.exceptions.SDKException("delete failed")

    with pytest.raises(UploadImageError) as exc:
        store.upload_image(
            arch=MagicMock(),
            cloud_name=MagicMock(),
            image_name="test-image",
            image_path=MagicMock(),
            keep_revisions=MagicMock(),
        )

    assert "missing the locally computed hashes" in str(exc.getrepr())


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
