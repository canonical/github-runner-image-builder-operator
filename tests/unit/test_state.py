# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for state module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

import os
import platform
import typing
from unittest.mock import MagicMock

import pytest
from ops.testing import Harness

import state
from charm import GithubRunnerImageBuilderCharm
from tests.unit import factories


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

    with pytest.raises(state.UnsupportedArchitectureError) as exc:
        state._get_supported_arch()

    assert arch in str(exc.getrepr())


@pytest.mark.parametrize(
    "arch, expected",
    [
        pytest.param("arm64", state.Arch.ARM64, id="arm64"),
        pytest.param("amd64", state.Arch.X64, id="amd64"),
    ],
)
def test_arch_from_charm(arch: str, expected: state.Arch):
    """
    arrange: given charm with architecture configurations.
    act: when Arch.from_charm is called.
    assert: expected architecture is returned.
    """
    charm = factories.MockCharmFactory()
    charm.config[state.ARCHITECTURE_CONFIG_NAME] = arch

    assert state.Arch.from_charm(charm=charm) == expected


@pytest.mark.parametrize(
    "arch, expected_arch",
    [
        pytest.param("aarch64", state.Arch.ARM64, id="aarch64"),
        pytest.param("arm64", state.Arch.ARM64, id="aarch64"),
        pytest.param("x86_64", state.Arch.X64, id="amd64"),
    ],
)
def test__get_supported_arch(
    arch: str, expected_arch: state.Arch, monkeypatch: pytest.MonkeyPatch
):
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
        pytest.param(state.Arch.ARM64, state.Arch.ARM64.value),
        pytest.param(state.Arch.X64, state.Arch.X64.value),
    ],
)
def test_arch_str(arch: state.Arch, expected_str: str):
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
    act: when state.BaseImage.from_charm is called.
    assert: InvalidBaseImageError is raised.
    """
    charm = factories.MockCharmFactory()
    charm.config[state.BASE_IMAGE_CONFIG_NAME] = image

    with pytest.raises(state.InvalidBaseImageError) as exc:
        state.BaseImage.from_charm(charm)

    assert image in str(exc)


@pytest.mark.parametrize(
    "image, expected_base_image",
    [
        pytest.param("jammy", (state.BaseImage.JAMMY,), id="jammy"),
        pytest.param("22.04", (state.BaseImage.JAMMY,), id="22.04"),
    ],
)
def test_base_image(image: str, expected_base_image: state.BaseImage):
    """
    arrange: given supported image name or tag as config value.
    act: when state.BaseImage.from_charm is called.
    assert: expected base image is returned.
    """
    charm = factories.MockCharmFactory()
    charm.config[state.BASE_IMAGE_CONFIG_NAME] = image

    assert state.BaseImage.from_charm(charm) == expected_base_image


@pytest.mark.parametrize(
    "base_image, expected_str",
    [
        pytest.param(state.BaseImage.JAMMY, state.BaseImage.JAMMY.value),
        pytest.param(state.BaseImage.NOBLE, state.BaseImage.NOBLE.value),
    ],
)
def test_base_image_str(base_image: state.BaseImage, expected_str: str):
    """
    arrange: given state.BaseImage enum.
    act: when string interpolation is called(__str__).
    assert: expected string representation is output.
    """
    assert str(base_image) == expected_str


def test_proxy_config(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched os.environ with juju proxy values.
    act: when ProxyConfig.from_env is called.
    assert: expected proxy config is returned.
    """
    monkeypatch.setattr(os, "getenv", MagicMock(return_value="test"))

    assert state.ProxyConfig.from_env() == state.ProxyConfig(
        http="test", https="test", no_proxy="test"
    )


@pytest.mark.parametrize(
    "flavor, network, expected_config",
    [
        pytest.param(
            "test-flavor",
            "",
            state.ExternalBuildConfig(flavor="test-flavor", network=""),
            id="flavor defined",
        ),
        pytest.param(
            "",
            "test-network",
            state.ExternalBuildConfig(flavor="", network="test-network"),
            id="network defined",
        ),
    ],
)
def test_external_build_config(
    flavor: str, network: str, expected_config: state.ExternalBuildConfig
):
    """
    arrange: given a mocked charm.
    act: when ExternalBuildConfig.from_charm is called.
    assert: expected build configs are returned.
    """
    charm = factories.MockCharmFactory()
    charm.config[state.EXTERNAL_BUILD_FLAVOR_CONFIG_NAME] = flavor
    charm.config[state.EXTERNAL_BUILD_NETWORK_CONFIG_NAME] = network

    assert state.ExternalBuildConfig.from_charm(charm=charm) == expected_config


def test_builder_run_config(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a valid charm configurations.
    act: when BuilderRunConfig.from_charm is called.
    assert: expected BuilderRunConfig is returned.
    """
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(os, "environ", {})

    charm = factories.MockCharmFactory()
    result = state.BuilderInitConfig.from_charm(charm)
    assert result == state.BuilderInitConfig(
        app_name=charm.app.name,
        channel=state.BuilderAppChannel.EDGE,
        external_build=True,
        run_config=state.BuilderRunConfig(
            cloud_config=state.CloudConfig(
                openstack_clouds_config=factories.OpenstackCloudsConfigFactory(),
                external_build_config=factories.ExternalBuildConfigFactory(),
                num_revisions=5,
            ),
            image_config=state.ImageConfig(
                arch=state.Arch.X64,
                bases=(state.BaseImage.JAMMY,),
                juju_channels=set(("", "3.1/stable", "2.9/stable")),
                microk8s_channels=set(("",)),
                prefix=charm.app.name,
                runner_version="1.234.5",
            ),
        ),
        interval=6,
        unit_name=charm.unit.name,
    )
    assert result.run_config.cloud_config.cloud_name == state.CLOUD_NAME


@pytest.mark.parametrize(
    "interval, expected_message",
    [
        pytest.param(
            "test", "An integer value for build-interval is expected.", id="not an integer"
        ),
        pytest.param(
            "-1", "Build interval must not be smaller than 1 or greater than 24", id="negative"
        ),
        pytest.param(
            "0", "Build interval must not be smaller than 1 or greater than 24", id="zero"
        ),
        pytest.param(
            "25",
            "Build interval must not be smaller than 1 or greater than 24",
            id="more than a day",
        ),
    ],
)
def test__parse_build_interval_invalid(interval: str, expected_message: str):
    """
    arrange: given an invalid interval.
    act: when _parse_build_interval is called.
    assert: BuildIntervalConfigError is raised.
    """
    charm = factories.MockCharmFactory()
    charm.config[state.BUILD_INTERVAL_CONFIG_NAME] = interval

    with pytest.raises(state.BuildIntervalConfigError) as exc:
        state._parse_build_interval(charm)

    assert expected_message in str(exc)


@pytest.mark.parametrize(
    "interval, expected",
    [
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
    charm = factories.MockCharmFactory()
    charm.config[state.BUILD_INTERVAL_CONFIG_NAME] = interval

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
    assert: InvalidRevisionHistoryLimitError is raised.
    """
    charm = factories.MockCharmFactory()
    charm.config[state.REVISION_HISTORY_LIMIT_CONFIG_NAME] = revision_history

    with pytest.raises(state.InvalidRevisionHistoryLimitError) as exc:
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
    charm = factories.MockCharmFactory()
    charm.config[state.REVISION_HISTORY_LIMIT_CONFIG_NAME] = revision_history

    assert state._parse_revision_history_limit(charm) == expected


@pytest.mark.parametrize(
    "version, expected_message",
    [
        pytest.param(
            "abc", "The runner version must be in semantic version format.", id="not a version"
        ),
        pytest.param(
            "1.20",
            "The runner version must be in semantic version format.",
            id="not a semantic version",
        ),
        pytest.param(
            "a.b.c",
            "The runner version numbers must be an integer.",
            id="non a integer versions",
        ),
        pytest.param(
            "1.20.-1",
            "The runner version numbers cannot be negative",
            id="not a semantic version (negative integer)",
        ),
        pytest.param(
            "v1.20.1", "The runner version numbers must be an integer", id="v char not accepted"
        ),
    ],
)
def test__parse_runner_version_invalid(version: str, expected_message: str):
    """
    arrange: given an invalid runner version config value.
    act: when _parse_runner_version is called.
    assert: ValueError is raised.
    """
    charm = factories.MockCharmFactory()
    charm.config[state.RUNNER_VERSION_CONFIG_NAME] = version

    with pytest.raises(ValueError) as exc:
        state._parse_runner_version(charm)

    assert expected_message in str(exc.getrepr())


@pytest.mark.parametrize(
    "version, expected_version",
    [
        pytest.param("", "", id="latest version"),
        pytest.param("1.234.5", "1.234.5", id="valid version"),
    ],
)
def test__parse_runner_version(version: str, expected_version: str):
    """
    arrange: given a valid runner version config value.
    act: when _parse_runner_version is called.
    assert: expected version number is returned.
    """
    charm = factories.MockCharmFactory()
    charm.config[state.RUNNER_VERSION_CONFIG_NAME] = version

    assert state._parse_runner_version(charm) == expected_version


@pytest.mark.parametrize(
    "missing_config",
    [
        pytest.param(state.OPENSTACK_AUTH_URL_CONFIG_NAME),
        pytest.param(state.OPENSTACK_PASSWORD_CONFIG_NAME),
        pytest.param(state.OPENSTACK_PROJECT_DOMAIN_CONFIG_NAME),
        pytest.param(state.OPENSTACK_PROJECT_CONFIG_NAME),
        pytest.param(state.OPENSTACK_USER_DOMAIN_CONFIG_NAME),
        pytest.param(state.OPENSTACK_USER_CONFIG_NAME),
    ],
)
def test__parse_openstack_clouds_config_invalid(missing_config: str):
    """
    arrange: given an invalid cloud config.
    act: when _parse_openstack_clouds_config is called.
    assert: InvalidCloudConfigError is raised.
    """
    charm = factories.MockCharmFactory()
    charm.config.pop(missing_config)

    with pytest.raises(state.InvalidCloudConfigError) as exc:
        state._parse_openstack_clouds_config(charm)

    assert "Please supply all OpenStack configurations." in str(exc)


def test__parse_openstack_clouds_config():
    """
    arrange: given mock charm from factory.
    act: when _parse_openstack_clouds_config is called.
    assert: expected clouds_config is returned.
    """
    charm = factories.MockCharmFactory()

    cloud_config = state._parse_openstack_clouds_config(charm=charm)
    assert cloud_config == state.OpenstackCloudsConfig(
        clouds={
            "builder": state._CloudsConfig(
                auth=state.CloudsAuthConfig(
                    auth_url="http://testing-auth/keystone",
                    # We're using testing password value from the factory.
                    password="test-password",  # nosec: B106:hardcoded_password_funcarg
                    project_domain_name="test-project-domain",
                    project_name="test-project-name",
                    user_domain_name="test-user-domain",
                    username="test-username",
                )
            )
        }
    )


# pylint: enable=undefined-variable,unused-variable


def test__parse_openstack_clouds_auth_configs_from_relation_no_units(
    harness: Harness, charm: GithubRunnerImageBuilderCharm, caplog: pytest.LogCaptureFixture
):
    """
    arrange: given an image relation with no units.
    act: when _parse_openstack_clouds_auth_configs_from_relation is called.
    assert: warning log is printed.
    """
    harness.add_relation(state.IMAGE_RELATION, "github-runner")

    state._parse_openstack_clouds_auth_configs_from_relation(charm=charm)

    assert any("Units not yet joined" in log_line for log_line in caplog.messages)


@pytest.mark.parametrize(
    "juju_config_value",
    [
        pytest.param("3.1/stable/", id="multiple slashes"),
        pytest.param("3.1", id="no risk"),
        pytest.param("/stable", id="no track"),
    ],
)
def test__parse_juju_channels_error(juju_config_value: str):
    """
    arrange: given invalid charm juju channel configurations.
    act: when _parse_juju_channels is called.
    assert: JujuChannelInvalidError is raised.
    """
    charm = factories.MockCharmFactory()
    charm.config[state.JUJU_CHANNELS_CONFIG_NAME] = juju_config_value

    with pytest.raises(state.JujuChannelInvalidError):
        state._parse_juju_channels(charm=charm)


@pytest.mark.parametrize(
    "juju_config_value",
    [
        pytest.param("3.1/stable/", id="multiple slashes"),
        pytest.param("3.1", id="no risk"),
        pytest.param("/stable", id="no track"),
    ],
)
def test__parse_microk8s_channels_error(juju_config_value: str):
    """
    arrange: given invalid charm juju channel configurations.
    act: when _parse_microk8s_channels is called.
    assert: Microk8sChannelInvalidError is raised.
    """
    charm = factories.MockCharmFactory()
    charm.config[state.MICROK8S_CHANNELS_CONFIG_NAME] = juju_config_value

    with pytest.raises(state.Microk8sChannelInvalidError):
        state._parse_microk8s_channels(charm=charm)


@pytest.mark.parametrize(
    "juju_config_value, expected_channels",
    [
        pytest.param("", set(("",)), id="no channels"),
        pytest.param("3.1/stable", set(("", "3.1/stable")), id="single channel"),
        pytest.param(
            "3.1/stable, 2.9/stable", set(("", "3.1/stable", "2.9/stable")), id="multiple channels"
        ),
    ],
)
def test__parse_juju_channels(juju_config_value: str, expected_channels: tuple[str, ...]):
    """
    arrange: given different charm juju channel configurations.
    act: when _parse_juju_channels is called.
    assert: expected juju channels are parsed.
    """
    charm = factories.MockCharmFactory()
    charm.config[state.JUJU_CHANNELS_CONFIG_NAME] = juju_config_value

    assert state._parse_juju_channels(charm=charm) == expected_channels


def test_builder_app_channel_from_charm_error():
    """
    arrange: given an invalid charm app channel config.
    act: when BuilderAppChannel.from_charm is called.
    assert: BuilderAppChannelInvalidError is raised.
    """
    charm = factories.MockCharmFactory()
    charm.config[state.APP_CHANNEL_CONFIG_NAME] = "invalid"

    with pytest.raises(state.BuilderAppChannelInvalidError) as exc:
        state.BuilderAppChannel.from_charm(charm=charm)

    assert "invalid" in str(exc.getrepr())


@pytest.mark.parametrize(
    "patch_obj, sub_func, exception, expected_message",
    [
        pytest.param(
            state,
            "_parse_build_interval",
            state.CharmConfigInvalidError("Invalid build interval"),
            "Invalid build interval",
            id="_parse_build_interval error",
        ),
        pytest.param(
            state,
            "_parse_openstack_clouds_config",
            state.CharmConfigInvalidError("Missing configuration"),
            "Missing configuration",
            id="_parse_openstack_clouds_config error",
        ),
        pytest.param(
            state,
            "_parse_revision_history_limit",
            state.CharmConfigInvalidError("Invalid revision history"),
            "Invalid revision history",
            id="_parse_revision_history_limit error",
        ),
    ],
)
def test_builder_init_config_invalid(
    patch_obj: typing.Any,
    sub_func: str,
    exception: typing.Type[Exception],
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
    charm = factories.MockCharmFactory()

    with pytest.raises(state.CharmConfigInvalidError) as exc:
        state.BuilderInitConfig.from_charm(charm)

    assert expected_message in str(exc.getrepr())
