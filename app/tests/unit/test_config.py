# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for state module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

import platform

import pytest

from github_runner_image_builder.config import (
    Arch,
    BaseImage,
    UnsupportedArchitectureError,
    get_supported_arch,
)


@pytest.mark.parametrize(
    "arch, expected",
    [
        pytest.param(Arch.ARM64, "aarch64", id="arm64"),
        pytest.param(Arch.X64, "x86_64", id="amd64"),
    ],
)
def test_arch_openstack_conversion(arch: Arch, expected: str):
    """
    arrange: given platform architecture.
    act: when arch.to_openstack is called.
    assert: expected Openstack architecture is returned.
    """
    assert arch.to_openstack() == expected


@pytest.mark.parametrize(
    "arch",
    [
        pytest.param("ppc64le", id="ppc64le"),
        pytest.param("mips", id="mips"),
        pytest.param("s390x", id="s390x"),
        pytest.param("testing", id="testing"),
    ],
)
def test_get_supported_arch_unsupported_arch(arch: str, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given architectures that are not supported by the app.
    act: when get_supported_arch is called.
    assert: UnsupportedArchitectureError is raised
    """
    monkeypatch.setattr(platform, "machine", lambda: arch)

    with pytest.raises(UnsupportedArchitectureError) as exc:
        get_supported_arch()

    assert arch in str(exc.getrepr())


@pytest.mark.parametrize(
    "arch, expected_arch",
    [
        pytest.param("aarch64", Arch.ARM64, id="aarch64"),
        pytest.param("arm64", Arch.ARM64, id="aarch64"),
        pytest.param("x86_64", Arch.X64, id="amd64"),
    ],
)
def test_get_supported_arch(arch: str, expected_arch: Arch, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given architectures that is supported by the app.
    act: when get_supported_arch is called.
    assert: expected architecture is returned.
    """
    monkeypatch.setattr(platform, "machine", lambda: arch)

    assert get_supported_arch() == expected_arch


@pytest.mark.parametrize(
    "image",
    [
        pytest.param("dingo", id="dingo"),
        pytest.param("focal", id="focal"),
        pytest.param("firefox", id="firefox"),
    ],
)
def test_base_image_invalid(image: str):
    """
    arrange: given invalid or unsupported base image names as config value.
    act: when BaseImage.from_str is called.
    assert: ValueError is raised.
    """
    with pytest.raises(ValueError) as exc:
        BaseImage.from_str(image)

    assert image in str(exc)


@pytest.mark.parametrize(
    "image, expected_base_image",
    [
        pytest.param("jammy", BaseImage.JAMMY, id="jammy"),
        pytest.param("22.04", BaseImage.JAMMY, id="22.04"),
    ],
)
def test_base_image(image: str, expected_base_image: BaseImage):
    """
    arrange: given supported image name or tag as config value.
    act: when BaseImage.from_str is called.
    assert: expected base image is returned.
    """
    assert BaseImage.from_str(image) == expected_base_image


@pytest.mark.parametrize(
    "base_image, expected_version",
    [
        pytest.param(BaseImage.JAMMY, "22.04", id="jammy"),
        pytest.param(BaseImage.NOBLE, "24.04", id="noble"),
    ],
)
def test_base_image_get_version(base_image: BaseImage, expected_version: str):
    """
    arrange: given base image enum instance.
    act: when BaseImage.get_version is called.
    assert: expected image version is returned.
    """
    assert BaseImage.get_version(base=base_image) == expected_version
