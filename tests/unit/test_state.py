# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for state module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

import platform
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

import state
from state import (
    BASE_IMAGE_CONFIG_NAME,
    BUILD_INTERVAL_CONFIG_NAME,
    OPENSTACK_CLOUDS_YAML_CONFIG_NAME,
    REVISION_HISTORY_LIMIT_CONFIG_NAME,
    Arch,
    BaseImage,
    CharmConfigInvalidError,
    ImageConfig,
    InvalidCloudConfigError,
    InvalidImageConfigError,
    ProxyConfig,
    UnsupportedArchitectureError,
    os,
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


@pytest.mark.parametrize(
    "interval, expected_message",
    [
        pytest.param(
            "test", "An integer value for build-interval is expected.", id="not an integer"
        ),
        pytest.param(
            "-1", "Build interval must not be negative or greater than 24", id="negative"
        ),
        pytest.param("0", "Build interval must not be negative or greater than 24", id="zero"),
        pytest.param(
            "25", "Build interval must not be negative or greater than 24", id="more than a day"
        ),
    ],
)
def test__parse_build_interval_invalid(interval: str, expected_message: str):
    """
    arrange: given an invalid interval.
    act: when _parse_build_interval is called.
    assert: ValueError is raised.
    """
    charm = MockCharmFactory()
    charm.config[BUILD_INTERVAL_CONFIG_NAME] = interval

    with pytest.raises(ValueError) as exc:
        state._parse_build_interval(charm)

    assert expected_message in str(exc)


@pytest.mark.parametrize(
    "interval, expected",
    [
        pytest.param("0", 0, id="don't build"),
        pytest.param("1", 1, id="valid interval (1)"),
        pytest.param("12", 12, id="valid interval (12)"),
        pytest.param("20", 20, id="valid interval (20)"),
        pytest.param("24", 24, id="valid interval (24)"),
    ],
)
def test__parse_build_interval(interval: str, expected: int):
    """
    arrange: given an valid interval.
    act: when _parse_build_interval is called.
    assert: expected interval is returned.
    """
    charm = MockCharmFactory()
    charm.config[BUILD_INTERVAL_CONFIG_NAME] = interval

    assert state._parse_build_interval(charm) == expected


@pytest.mark.parametrize(
    "revision_history, expected_err",
    [
        pytest.param("test", "An integer value for revision history is expected", id="non-int"),
        pytest.param(
            "-1", "Revision history must be greater than 1 and less than 100", id="negative"
        ),
        pytest.param("0", "Revision history must be greater than 1 and less than 100", id="zero"),
        pytest.param(
            "1", "Revision history must be greater than 1 and less than 100", id="too few"
        ),
        pytest.param(
            "100", "Revision history must be greater than 1 and less than 100", id="too many"
        ),
    ],
)
def test__parse_revision_history_limit_invalid(revision_history: str, expected_err: str):
    """
    arrange: given an invalid revision history config value.
    act: when _parse_revision_history_limit is called.
    assert: ValueError is raised.
    """
    charm = MockCharmFactory()
    charm.config[REVISION_HISTORY_LIMIT_CONFIG_NAME] = revision_history

    with pytest.raises(ValueError) as exc:
        state._parse_revision_history_limit(charm)

    assert expected_err in str(exc)


@pytest.mark.parametrize(
    "revision_history, expected",
    [
        pytest.param("2", 2, id="minimum"),
        pytest.param("10", 10, id="valid"),
        pytest.param("99", 99, id="maximum"),
    ],
)
def test__parse_revision_history_limit(revision_history: str, expected: int):
    """
    arrange: given a valid revision history config value.
    act: when _parse_revision_history_limit is called.
    assert: expected value is returned.
    """
    charm = MockCharmFactory()
    charm.config[REVISION_HISTORY_LIMIT_CONFIG_NAME] = revision_history

    assert state._parse_revision_history_limit(charm) == expected


@pytest.mark.parametrize(
    "cloud_config, expected_err",
    [
        pytest.param("", "No cloud config set", id="Not set"),
        pytest.param("""- not\nvalid""", "Invalid yaml", id="Not a yaml"),
        pytest.param('- "not"\n- "a"\n- "dict"\n', "expected dict", id="Not a dict"),
        pytest.param(
            yaml.dump({"no-clouds-key": "test"}), "Invalid openstack config", id="No clouds key"
        ),
        pytest.param(yaml.dump({"clouds": {}}), "No clouds", id="No clouds"),
    ],
)
def test__parse_openstack_clouds_config_invalid(cloud_config: str, expected_err: str):
    """
    arrange: given an invalid cloud config.
    act: when _parse_openstack_clouds_config is called.
    assert: InvalidCloudConfigError is raised.
    """
    charm = MockCharmFactory()
    charm.config[OPENSTACK_CLOUDS_YAML_CONFIG_NAME] = cloud_config

    with pytest.raises(InvalidCloudConfigError) as exc:
        state._parse_openstack_clouds_config(charm)

    assert expected_err in str(exc)


# pylint doesn't quite understand walrus operators
# pylint: disable=unused-variable,undefined-variable
@pytest.mark.parametrize(
    "cloud_config, expected",
    [
        pytest.param(
            yaml.dump((expected := {"clouds": {"sunbeam": {"expected": "key "}}})),
            expected,
            id="one cloud",
        ),
        pytest.param(
            yaml.dump((expected := {"clouds": {"sunbeam": {"expected": "key "}}, "another": {}})),
            expected,
            id="multi clouds",
        ),
    ],
)
def test__parse_openstack_clouds_config(cloud_config: str, expected: dict):
    """
    arrange: given a valid cloud config.
    act: when _parse_openstack_clouds_config is called.
    assert: expected cloud config is returned.
    """
    charm = MockCharmFactory()
    charm.config[OPENSTACK_CLOUDS_YAML_CONFIG_NAME] = cloud_config

    assert state._parse_openstack_clouds_config(charm) == expected


def test_proxy_config(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched os.environ with juju proxy values.
    act: when ProxyConfig.from_env is called.
    assert: expected proxy config is returned.
    """
    monkeypatch.setattr(os, "getenv", MagicMock(return_value="test"))

    assert ProxyConfig.from_env() == ProxyConfig(http="test", https="test", no_proxy="test")


@pytest.mark.parametrize(
    "patch_obj, sub_func, exception, expected_message",
    [
        pytest.param(
            state.ImageConfig,
            "from_charm",
            InvalidImageConfigError("Invalid image"),
            "Invalid image",
            id="ImageConfig error",
        ),
        pytest.param(
            state,
            "_parse_build_interval",
            ValueError("Invalid build interval"),
            "Invalid build interval",
            id="_parse_build_interval error",
        ),
        pytest.param(
            state,
            "_parse_openstack_clouds_config",
            InvalidCloudConfigError("Invalid clouds yaml"),
            "Invalid clouds yaml",
            id="_parse_openstack_clouds_config error",
        ),
        pytest.param(
            state,
            "_parse_revision_history_limit",
            ValueError("Invalid revision history"),
            "Invalid revision history",
            id="_parse_revision_history_limit error",
        ),
    ],
)
def test_charm_state_invalid(
    patch_obj: Any,
    sub_func: str,
    exception: Exception,
    expected_message: str,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: given a monkeypatched sub functions of CharmState that raises given exceptions.
    act: when CharmState.from_charm is called.
    assert: A CharmConfigInvalidError is raised.
    """
    mock_func = MagicMock(side_effect=exception)
    monkeypatch.setattr(patch_obj, sub_func, mock_func)
    charm = MockCharmFactory()

    with pytest.raises(CharmConfigInvalidError) as exc:
        state.CharmState.from_charm(charm)

    assert expected_message in str(exc.getrepr())


def test_charm_state(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a valid charm configurations.
    act: when CharmState.from_charm is called.
    assert: charm state is returned.
    """
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(os, "environ", {})

    charm = MockCharmFactory()
    result = state.CharmState.from_charm(charm)
    assert result == state.CharmState(
        build_interval=int(charm.config[BUILD_INTERVAL_CONFIG_NAME]),
        cloud_config=yaml.safe_load(charm.config[OPENSTACK_CLOUDS_YAML_CONFIG_NAME]),
        image_config=ImageConfig(
            arch=Arch.X64, base_image=BaseImage(charm.config[BASE_IMAGE_CONFIG_NAME])
        ),
        proxy_config=None,
        revision_history_limit=int(charm.config[REVISION_HISTORY_LIMIT_CONFIG_NAME]),
    )
    assert result.cloud_name == "sunbeam"
