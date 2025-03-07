# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for state module."""

# Need access to protected functions for testing
# pylint:disable=protected-access


import pytest

from github_runner_image_builder.config import (
    Arch,
    BaseImage,
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
    "image",
    [
        pytest.param("dingo", id="dingo"),
        pytest.param("bionic", id="bionic"),
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
        pytest.param(BaseImage.FOCAL, "20.04", id="focal"),
        pytest.param(BaseImage.JAMMY, "22.04", id="jammy"),
        pytest.param(BaseImage.NOBLE, "24.04", id="noble"),
        pytest.param(None, None, id="None"),
    ],
)
def test_base_image_get_version(base_image: BaseImage, expected_version: str):
    """
    arrange: given base image enum instance.
    act: when BaseImage.get_version is called.
    assert: expected image version is returned.
    """
    assert BaseImage.get_version(base=base_image) == expected_version
