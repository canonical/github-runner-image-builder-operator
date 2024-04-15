# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import platform
from typing import Any
from unittest.mock import MagicMock

import pytest

import state
from state import (
    BASE_IMAGE_CONFIG_NAME,
    Arch,
    BaseImage,
    ImageConfig,
    InvalidImageConfigError,
    UnsupportedArchitectureError,
)
from tests.unit.factories import MockCharmFactory


@pytest.mark.parametrize(
    "arch",
    [
        pytest.param("ppc64le", id="ppc64le"),
        pytest.param("mips", id="mips"),
        pytest.param("s390x", id="s390x"),
        pytest.param("testing", id="testing"),
    ],
)
def test__get_supported_arch_unsupported_arch(arch: str, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given architectures that are not supported by the charm.
    act: when _get_supported_arch is called.
    assert: UnsupportedArchitectureError is raised
    """
    monkeypatch.setattr(platform, "machine", lambda: arch)

    with pytest.raises(UnsupportedArchitectureError) as exc:
        state._get_supported_arch()

    assert arch in str(exc.getrepr())


@pytest.mark.parametrize(
    "arch, expected_arch",
    [
        pytest.param("aarch64", Arch.ARM64, id="aarch64"),
        pytest.param("arm64", Arch.ARM64, id="aarch64"),
        pytest.param("x86_64", Arch.X64, id="amd64"),
    ],
)
def test__get_supported_arch(arch: str, expected_arch: Arch, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given architectures that is supported by the charm.
    act: when _get_supported_arch is called.
    assert: expected architecture is returned.
    """
    monkeypatch.setattr(platform, "machine", lambda: arch)

    assert state._get_supported_arch() == expected_arch


@pytest.mark.parametrize(
    "arch, expected_str",
    [
        pytest.param(Arch.ARM64, Arch.ARM64.value),
        pytest.param(Arch.X64, Arch.X64.value),
    ],
)
def test_arch_str(arch: Arch, expected_str: str):
    """
    arrange: given arch enum.
    act: when string interpolation is called(__str__).
    assert: expected string representation is output.
    """
    assert str(arch) == expected_str


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
    act: when BaseImage.from_charm is called.
    assert: ValueError is raised.
    """
    charm = MockCharmFactory()
    charm.config[BASE_IMAGE_CONFIG_NAME] = image

    with pytest.raises(ValueError) as exc:
        BaseImage.from_charm(charm)

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
    act: when BaseImage.from_charm is called.
    assert: expected base image is returned.
    """
    charm = MockCharmFactory()
    charm.config[BASE_IMAGE_CONFIG_NAME] = image

    assert BaseImage.from_charm(charm) == expected_base_image


@pytest.mark.parametrize(
    "base_image, expected_str",
    [
        pytest.param(BaseImage.JAMMY, BaseImage.JAMMY.value),
        pytest.param(BaseImage.NOBLE, BaseImage.NOBLE.value),
    ],
)
def test_base_image_str(base_image: BaseImage, expected_str: str):
    """
    arrange: given BaseImage enum.
    act: when string interpolation is called(__str__).
    assert: expected string representation is output.
    """
    assert str(base_image) == expected_str


@pytest.mark.parametrize(
    "patch_obj, sub_func, exception, expected_message",
    [
        pytest.param(
            state,
            "_get_supported_arch",
            UnsupportedArchitectureError(arch=""),
            "Unsupported architecture",
            id="unsupported arch",
        ),
        pytest.param(
            state.BaseImage,
            "from_charm",
            ValueError,
            "Unsupported input option for base-image",
            id="unsupported base image",
        ),
    ],
)
def test_image_config_invalid(
    patch_obj: Any,
    sub_func: str,
    exception: Exception,
    expected_message: str,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: given a monkeypatched sub functions of ImageConfig that raises given exceptions.
    act: when ImageConfig.from_charm is called.
    assert: An InvalidImageConfigError is raised.
    """
    mock_func = MagicMock(side_effect=exception)
    monkeypatch.setattr(patch_obj, sub_func, mock_func)

    with pytest.raises(InvalidImageConfigError) as exc:
        ImageConfig.from_charm(MagicMock)

    assert expected_message in str(exc)


def test_image_config(
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: given a monkeypatched sub functions of ImageConfig.
    act: when ImageConfig.from_charm is called.
    assert: valid class config is returned.
    """
    test_arch = MagicMock(return_value=Arch.ARM64)
    test_image = MagicMock(return_value=BaseImage.JAMMY)
    monkeypatch.setattr(state, "_get_supported_arch", test_arch)
    monkeypatch.setattr(state.BaseImage, "from_charm", test_image)

    assert ImageConfig.from_charm(MagicMock) == ImageConfig(
        arch=test_arch.return_value, base_image=test_image.return_value
    )
