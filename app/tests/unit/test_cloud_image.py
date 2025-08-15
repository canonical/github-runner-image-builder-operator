# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for cloud_image module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

import time
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from github_runner_image_builder import cloud_image
from github_runner_image_builder.cloud_image import (
    Arch,
    BaseImage,
    BaseImageDownloadError,
    SupportedBaseImageArch,
    UnsupportedArchitectureError,
)


@pytest.mark.parametrize(
    "patch_obj, sub_func, exception, expected_message",
    [
        pytest.param(
            cloud_image,
            "_get_supported_runner_arch",
            UnsupportedArchitectureError("Unsupported architecture"),
            "Unsupported architecture",
            id="Unsupported architecture",
        ),
        pytest.param(
            cloud_image,
            "_download_base_image",
            BaseImageDownloadError("Content too short"),
            "Content too short",
            id="Network interrupted",
        ),
        pytest.param(
            cloud_image,
            "_fetch_shasums",
            BaseImageDownloadError("Content too short"),
            "Content too short",
            id="Network interrupted (SHASUM)",
        ),
    ],
)
def test__download_and_validate_image_error(
    patch_obj: Any,
    sub_func: str,
    exception: Exception,
    expected_message: str,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: given monkeypatched sub functions of _download_and_validate_image that raises \
        exceptions.
    act: when _download_and_validate_image is called.
    assert: A BaseImageDownloadError is raised.
    """
    mock_func = MagicMock(side_effect=exception)
    monkeypatch.setattr(cloud_image, "_get_supported_runner_arch", MagicMock)
    monkeypatch.setattr(cloud_image, "_download_base_image", MagicMock)
    monkeypatch.setattr(cloud_image, "_fetch_shasums", MagicMock)
    monkeypatch.setattr(cloud_image, "_validate_checksum", MagicMock)
    monkeypatch.setattr(patch_obj, sub_func, mock_func)

    with pytest.raises(BaseImageDownloadError) as exc:
        cloud_image.download_and_validate_image(arch=MagicMock(), base_image=MagicMock())

    assert expected_message in str(exc.getrepr())


def test__download_and_validate_image_no_shasum(
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: given monkeypatched _fetch_shasums that returns empty shasums.
    act: when _download_and_validate_image is called.
    assert: A BaseImageDownloadError is raised.
    """
    monkeypatch.setattr(cloud_image, "_get_supported_runner_arch", MagicMock())
    monkeypatch.setattr(cloud_image, "_download_base_image", MagicMock())
    monkeypatch.setattr(cloud_image, "_fetch_shasums", MagicMock(return_value={}))

    with pytest.raises(BaseImageDownloadError) as exc:
        cloud_image.download_and_validate_image(arch=MagicMock(), base_image=MagicMock())

    assert "Corresponding checksum not found." in str(exc.getrepr())


def test_download_and_validate_image_invalid_checksum(
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: given monkeypatched _validate_checksum that returns false.
    act: when download_and_validate_image is called.
    assert: A BaseImageDownloadError is raised.
    """
    monkeypatch.setattr(cloud_image, "_get_supported_runner_arch", MagicMock(return_value="x64"))
    monkeypatch.setattr(cloud_image, "_download_base_image", MagicMock())
    monkeypatch.setattr(
        cloud_image,
        "_fetch_shasums",
        MagicMock(return_value={"jammy-server-cloudimg-x64.img": "test"}),
    )
    monkeypatch.setattr(cloud_image, "_validate_checksum", MagicMock(return_value=False))

    with pytest.raises(BaseImageDownloadError) as exc:
        cloud_image.download_and_validate_image(arch=Arch.X64, base_image=BaseImage.JAMMY)

    assert "Invalid checksum." in str(exc.getrepr())


def test_download_and_validate_image(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched sub functions of download_and_validate_image.
    act: when download_and_validate_image is called.
    assert: the mocked subfunctions are called.
    """
    monkeypatch.setattr(
        cloud_image, "_get_supported_runner_arch", get_arch_mock := MagicMock(return_value="x64")
    )
    monkeypatch.setattr(cloud_image, "_download_base_image", download_base_mock := MagicMock())
    monkeypatch.setattr(
        cloud_image,
        "_fetch_shasums",
        fetch_shasums_mock := MagicMock(return_value={"jammy-server-cloudimg-x64.img": "test"}),
    )
    monkeypatch.setattr(cloud_image, "_validate_checksum", validate_checksum_mock := MagicMock())

    cloud_image.download_and_validate_image(arch=Arch.X64, base_image=BaseImage.JAMMY)

    get_arch_mock.assert_called_once()
    download_base_mock.assert_called_once()
    fetch_shasums_mock.assert_called_once()
    validate_checksum_mock.assert_called_once()


def test__get_supported_runner_arch_unsupported_error():
    """
    arrange: given an architecture value that isn't supported.
    act: when _get_supported_runner_arch is called.
    assert: UnsupportedArchitectureError is raised.
    """
    arch = MagicMock()
    with pytest.raises(UnsupportedArchitectureError):
        cloud_image._get_supported_runner_arch(arch)


@pytest.mark.parametrize(
    "arch, expected",
    [
        pytest.param(Arch.ARM64, "arm64", id="ARM64"),
        pytest.param(Arch.X64, "amd64", id="AMD64"),
        pytest.param(Arch.S390X, "s390x", id="S390X"),
        pytest.param(Arch.PPC64LE, "ppc64el", id="PPC64LE"),
    ],
)
def test__get_supported_runner_arch(arch: Arch, expected: SupportedBaseImageArch):
    """
    arrange: given an architecture value that is supported.
    act: when _get_supported_runner_arch is called.
    assert: Expected architecture in cloud_images format is returned.
    """
    assert cloud_image._get_supported_runner_arch(arch) == expected


def test__download_base_image_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched urlretrieve function that raises an error.
    act: when _download_base_image is called.
    assert: BaseImageDownloadError is raised.
    """
    # Bypass decorated retry sleep
    monkeypatch.setattr(time, "sleep", MagicMock())
    monkeypatch.setattr(
        cloud_image.requests,
        "get",
        MagicMock(side_effect=cloud_image.requests.exceptions.HTTPError()),
    )

    with pytest.raises(BaseImageDownloadError):
        cloud_image._download_base_image(
            base_image=MagicMock(), bin_arch=MagicMock(), output_filename=MagicMock()
        )


def test__download_base_image(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """
    arrange: given monkeypatched urlretrieve function.
    act: when _download_base_image is called.
    assert: Path from output_filename input is returned.
    """
    response_mock = MagicMock()
    response_mock.iter_content.return_value = [b"content-1", b"content-2"]
    monkeypatch.setattr(cloud_image.requests, "get", MagicMock(return_value=response_mock))
    test_file = tmp_path / "test_file_name"

    assert (
        test_file.name
        == cloud_image._download_base_image(
            base_image=MagicMock(), bin_arch=MagicMock(), output_filename=str(test_file)
        ).name
    )

def test__download_base_image_release_date(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """
    arrange: given monkeypatched urlretrieve function.
    act: when _download_base_image is called with a release date.
    assert: request mock is called with the correct URL
    """
    response_mock = MagicMock()
    response_mock.iter_content.return_value = [b"content-1", b"content-2"]
    monkeypatch.setattr(cloud_image.requests, "get", MagicMock(return_value=response_mock))
    test_file = tmp_path / "test_file_name"
    release_date = date(2025, 7, 25)

    cloud_image._download_base_image(
        base_image=BaseImage.JAMMY, bin_arch=Arch.ARM64.value, output_filename=str(test_file), release_date=release_date
    )

    cloud_image.requests.get.assert_called_once_with(
        f"https://cloud-images.ubuntu.com/jammy/20250725/jammy-server-cloudimg-arm64.img",
        timeout=60 * 20,
        stream=True,
    )


def test__fetch_shasums_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched requests function that raises an error.
    act: when _fetch_shasums is called.
    assert: BaseImageDownloadError is raised.
    """
    # Bypass decorated retry sleep
    monkeypatch.setattr(time, "sleep", MagicMock())
    monkeypatch.setattr(
        cloud_image.requests,
        "get",
        MagicMock(side_effect=cloud_image.requests.RequestException("Content too short")),
    )

    with pytest.raises(BaseImageDownloadError) as exc:
        cloud_image._fetch_shasums(base_image=MagicMock())

    assert "Content too short" in str(exc.getrepr())


def test__fetch_shasums(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched requests function that returns mocked contents of SHA256SUMS.
    act: when _fetch_shasums is called.
    assert: a dictionary with filename to shasum is created.
    """
    # Bypass decorated retry sleep
    monkeypatch.setattr(time, "sleep", MagicMock())
    mock_response = MagicMock()
    mock_response.content = bytes(
        """test_shasum1 *file1
test_shasum2 *file2
test_shasum3 *file3
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(cloud_image.requests, "get", MagicMock(return_value=mock_response))

    assert {
        "file1": "test_shasum1",
        "file2": "test_shasum2",
        "file3": "test_shasum3",
    } == cloud_image._fetch_shasums(base_image=MagicMock())


@pytest.mark.parametrize(
    "content, checksum, expected",
    [
        pytest.param(
            "sha256sumteststring",
            "52b60ec50ea69cd09d5f25b75c295b93181eaba18444fdbc537beee4653bad7e",
            True,
        ),
        pytest.param("test", "test", False),
    ],
)
def test__validate_checksum(tmp_path: Path, content: str, checksum: str, expected: bool):
    """
    arrange: given a file content and a checksum pair.
    act: when _validate_checksum is called.
    assert: expected result is returned.
    """
    test_path = tmp_path / "test"
    test_path.write_text(content, encoding="utf-8")

    assert expected == cloud_image._validate_checksum(test_path, checksum)
