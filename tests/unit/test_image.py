# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for image observer module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

import typing
from unittest.mock import MagicMock

import pytest

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
    assert: no image ready warning is logged.
    """
    monkeypatch.setattr(state.BuilderRunConfig, "from_charm", MagicMock())
    monkeypatch.setattr(image.builder, "get_latest_image", MagicMock(return_value=[]))

    observer = image.Observer(MagicMock())
    observer._on_image_relation_joined(MagicMock())

    assert caplog.messages
    assert all("No images ready." in log for log in caplog.messages)


def test__on_image_relation_joined_missing_images(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    """
    arrange: given a monkeypatched OpenstackManager.get_latest_image_id that returns images with \
        no id.
    act: when _on_image_relation_joined hook is fired.
    assert: image not ready warning is logged.
    """
    monkeypatch.setattr(state.BuilderRunConfig, "from_charm", MagicMock())
    monkeypatch.setattr(
        image.builder,
        "get_latest_image",
        MagicMock(return_value=[(test_result_mock := MagicMock())]),
    )
    test_result_mock.id = ""

    observer = image.Observer(MagicMock())
    observer._on_image_relation_joined(MagicMock())

    assert caplog.messages
    assert all("Not all images ready." in log for log in caplog.messages)


def test__on_image_relation_joined(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched OpenstackManager.get_latest_image_id that returns an image ID.
    act: when _on_image_relation_joined hook is fired.
    assert: update_relation_data is called.
    """
    monkeypatch.setattr(state.BuilderRunConfig, "from_charm", MagicMock())
    monkeypatch.setattr(
        image.builder, "get_latest_image", MagicMock(return_value=[image_mock := MagicMock()])
    )
    image_mock.id = "test-id"

    observer = image.Observer(MagicMock())
    observer.update_image_data = (update_relation_data_mock := MagicMock())
    observer._on_image_relation_joined(MagicMock())

    update_relation_data_mock.assert_called()


@pytest.mark.parametrize(
    "results, expected_relation_data",
    [
        pytest.param(
            (
                builder.BuildResult(
                    config=builder.BuildConfig(
                        arch=state.Arch.ARM64,
                        base=state.BaseImage.JAMMY,
                        cloud_config=MagicMock(),
                        num_revisions=1,
                        runner_version="",
                    ),
                    id="test-id",
                ),
            ),
            image.ImageRelationData(id="test-id", tags="arm64,jammy", custom="[]"),
            id="builder result",
        ),
        pytest.param(
            (
                builder.GetLatestImageResult(
                    config=builder.GetLatestImageConfig(
                        arch=state.Arch.ARM64, base=state.BaseImage.JAMMY, cloud_name="test-cloud"
                    ),
                    id="test-id",
                ),
            ),
            image.ImageRelationData(id="test-id", tags="arm64,jammy", custom="[]"),
            id="get image result",
        ),
        pytest.param(
            (
                builder.BuildResult(
                    config=builder.BuildConfig(
                        arch=state.Arch.ARM64,
                        base=state.BaseImage.JAMMY,
                        cloud_config=MagicMock(),
                        num_revisions=1,
                        runner_version="",
                    ),
                    id="test-id-1",
                ),
                builder.BuildResult(
                    config=builder.BuildConfig(
                        arch=state.Arch.ARM64,
                        base=state.BaseImage.NOBLE,
                        cloud_config=MagicMock(),
                        num_revisions=1,
                        runner_version="",
                    ),
                    id="test-id-2",
                ),
            ),
            image.ImageRelationData(
                id="test-id-1",
                tags="arm64,jammy",
                custom='[{"id":"test-id-2","tags":"arm64,noble"}]',
            ),
            id="multiple builder results",
        ),
        pytest.param(
            (
                builder.GetLatestImageResult(
                    config=builder.GetLatestImageConfig(
                        arch=state.Arch.ARM64, base=state.BaseImage.JAMMY, cloud_name="test-cloud"
                    ),
                    id="test-id-1",
                ),
                builder.GetLatestImageResult(
                    config=builder.GetLatestImageConfig(
                        arch=state.Arch.ARM64, base=state.BaseImage.NOBLE, cloud_name="test-cloud"
                    ),
                    id="test-id-2",
                ),
            ),
            image.ImageRelationData(
                id="test-id-1",
                tags="arm64,jammy",
                custom='[{"id":"test-id-2","tags":"arm64,noble"}]',
            ),
            id="multiple get image results",
        ),
    ],
)
def test_update_relation_data(
    monkeypatch: pytest.MonkeyPatch,
    results: typing.Iterable[builder.BuildResult | builder.GetLatestImageResult],
    expected_relation_data: image.ImageRelationData,
):
    """
    arrange: given a monkeypatched OpenstackManager.get_latest_image_id that returns an image ID.
    act: when _on_image_relation_joined hook is fired.
    assert: update_relation_data is called.
    """
    monkeypatch.setattr(state.BuilderRunConfig, "from_charm", MagicMock())
    observer = image.Observer(MagicMock())
    observer.model.relations = {state.IMAGE_RELATION: [(relation := MagicMock())]}

    observer.update_image_data(results=results)

    relation.data[observer.model.unit].update.called_once_with(expected_relation_data)


def test__to_image_relation_data_no_results():
    """
    arrange: given no image result data from build/get latest image call.
    act: when _to_image_relation_data is called.
    assert: ValueError is raised.
    """
    observer = image.Observer(MagicMock())

    with pytest.raises(ValueError) as exc:
        observer._to_image_relation_data(results=[])

    assert "Builds output must be greater than 0." in str(exc)
