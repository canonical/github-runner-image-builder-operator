# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for charm module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

from unittest.mock import MagicMock

import ops
import pytest

import builder
import image
import proxy
import state
from charm import GithubRunnerImageBuilderCharm


@pytest.fixture(name="charm", scope="module")
def charm_fixture():
    """Mock charm fixture w/ framework."""
    # this is required since current ops does not support charmcraft.yaml
    mock_framework = MagicMock(spec=ops.framework.Framework)
    mock_framework.meta.actions = ["run"]
    mock_framework.meta.relations = ["image"]
    charm = GithubRunnerImageBuilderCharm(mock_framework)
    return charm


@pytest.fixture(name="patch_builder_init_config_from_charm", scope="function")
def patch_builder_init_config_from_charm(monkeypatch: pytest.MonkeyPatch):
    """Fixture to patch builder init config."""
    monkeypatch.setattr(
        state.BuilderInitConfig,
        "from_charm",
        MagicMock(
            return_value=state.BuilderInitConfig(
                channel=MagicMock(),
                external_build=True,
                interval=1,
                run_config=state.BuilderRunConfig(
                    arch=MagicMock(),
                    base=MagicMock(),
                    cloud_config=state.OpenstackCloudsConfig(
                        clouds={
                            state.UPLOAD_CLOUD_NAME: state._CloudsConfig(
                                auth=MagicMock(), region_name="test"
                            )
                        }
                    ),
                    external_build_config=MagicMock(),
                    num_revisions=1,
                    runner_version="test-version",
                ),
                unit_name="test-unit",
            )
        ),
    )


@pytest.mark.parametrize(
    "hook",
    [
        pytest.param("_on_config_changed", id="config_changed"),
        pytest.param("_on_run_action", id="run_action"),
        pytest.param("_on_image_relation_changed", id="image_relation_changed"),
    ],
)
def test_block_on_image_relation_not_ready(
    monkeypatch: pytest.MonkeyPatch, charm: GithubRunnerImageBuilderCharm, hook: str
):
    """
    arrange: given hooks that should not run build when image relation is not yet ready.
    act: when the hook is called.
    assert: the charm falls into BlockedStatus.
    """
    monkeypatch.setattr(state.BuilderInitConfig, "from_charm", MagicMock())
    monkeypatch.setattr(state.BuilderRunConfig, "from_charm", MagicMock())
    getattr(charm, hook)(MagicMock())

    assert charm.unit.status == ops.BlockedStatus(f"{state.IMAGE_RELATION} integration required.")


@pytest.mark.parametrize(
    "hook",
    [
        pytest.param("_on_install", id="_on_install"),
        pytest.param("_on_config_changed", id="_on_config_changed"),
        pytest.param("_on_run_action", id="_on_run_action"),
    ],
)
def test_block_on_state_error(
    monkeypatch: pytest.MonkeyPatch, hook: str, charm: GithubRunnerImageBuilderCharm
):
    """
    arrange: given a monkeypatched CharmState.from_charm that raises CharmConfigInvalidError.
    act: when _load_state is called.
    assert: charm is in blocked status.
    """
    monkeypatch.setattr(image, "Observer", MagicMock())
    monkeypatch.setattr(
        state.BuilderInitConfig,
        "from_charm",
        MagicMock(side_effect=state.CharmConfigInvalidError("Invalid config")),
    )
    monkeypatch.setattr(
        state.BuilderRunConfig,
        "from_charm",
        MagicMock(side_effect=state.CharmConfigInvalidError("Invalid config")),
    )

    getattr(charm, hook)(MagicMock())

    assert charm.unit.status == ops.BlockedStatus("Invalid config")


def test__on_install(monkeypatch: pytest.MonkeyPatch, charm: GithubRunnerImageBuilderCharm):
    """
    arrange: given a monekypatched builder.setup_builder function.
    act: when _on_install is called.
    assert: setup_builder is called.
    """
    monkeypatch.setattr(state.BuilderInitConfig, "from_charm", MagicMock())
    monkeypatch.setattr(state.BuilderRunConfig, "from_charm", MagicMock())
    monkeypatch.setattr(image, "Observer", MagicMock())
    monkeypatch.setattr(proxy, "setup", MagicMock())
    monkeypatch.setattr(proxy, "configure_aproxy", MagicMock())
    monkeypatch.setattr(builder, "initialize", (setup_mock := MagicMock()))

    charm._on_install(MagicMock())

    setup_mock.assert_called_once()
    assert charm.unit.status == ops.ActiveStatus("Waiting for first image.")


@pytest.mark.usefixtures("patch_builder_init_config_from_charm")
@pytest.mark.parametrize(
    "configure_cron",
    [
        pytest.param(False, id="No reconfiguration"),
        pytest.param(True, id="Reconfigure"),
    ],
)
def test__on_config_changed(
    monkeypatch: pytest.MonkeyPatch, charm: GithubRunnerImageBuilderCharm, configure_cron: bool
):
    """
    arrange: given monkeypatched builder, openstack manager, image_observer.
    act: when _on_config_changed is called.
    assert: charm is in active status.
    """
    monkeypatch.setattr(state.BuilderRunConfig, "from_charm", MagicMock())
    monkeypatch.setattr(
        image, "Observer", MagicMock(return_value=(image_observer_mock := MagicMock()))
    )
    monkeypatch.setattr(proxy, "configure_aproxy", MagicMock())
    monkeypatch.setattr(builder, "install_clouds_yaml", MagicMock())
    monkeypatch.setattr(builder, "configure_cron", MagicMock(return_value=configure_cron))
    monkeypatch.setattr(builder, "run", MagicMock())
    monkeypatch.setattr(builder, "upgrade_app", MagicMock())
    charm.image_observer = image_observer_mock

    charm._on_config_changed(MagicMock())

    assert charm.unit.status == ops.ActiveStatus()


def test__on_image_relation_changed(
    monkeypatch: pytest.MonkeyPatch, charm: GithubRunnerImageBuilderCharm
):
    """
    arrange: given monkeypatched builder, openstack manager, image_observer.
    act: when _on_image_relation_changed is called.
    assert: charm is in active status.
    """
    mock_init_config = MagicMock()
    mock_init_config.run_config = (run_config := MagicMock())
    run_config.cloud_config = state.OpenstackCloudsConfig(
        clouds={state.UPLOAD_CLOUD_NAME: state._CloudsConfig(auth="non-empty")}
    )
    monkeypatch.setattr(
        state.BuilderInitConfig, "from_charm", MagicMock(return_value=mock_init_config)
    )
    monkeypatch.setattr(state.BuilderRunConfig, "from_charm", MagicMock())
    monkeypatch.setattr(
        image, "Observer", MagicMock(return_value=(image_observer_mock := MagicMock()))
    )
    monkeypatch.setattr(proxy, "configure_aproxy", MagicMock())
    monkeypatch.setattr(builder, "install_clouds_yaml", MagicMock())
    monkeypatch.setattr(builder, "run", MagicMock())
    monkeypatch.setattr(builder, "upgrade_app", MagicMock())
    charm.image_observer = image_observer_mock

    charm._on_image_relation_changed(MagicMock())

    assert charm.unit.status == ops.ActiveStatus()


@pytest.mark.usefixtures("patch_builder_init_config_from_charm")
def test__on_run_action(charm: GithubRunnerImageBuilderCharm):
    """
    arrange: given a mocked functions of _on_run_action.
    act: when _on_run_action is called.
    assert: subfunctions are called.
    """
    charm._run = (run_mock := MagicMock())

    charm._on_run_action(MagicMock())

    run_mock.assert_called()


@pytest.mark.parametrize(
    "config, expected_return",
    [
        pytest.param(
            state.BuilderRunConfig(
                arch=state.Arch.ARM64,
                base=state.BaseImage.JAMMY,
                cloud_config=state.OpenstackCloudsConfig(clouds={}),
                external_build_config=None,
                num_revisions=1,
                runner_version="test",
            ),
            False,
            id="missiong integration",
        ),
        pytest.param(
            state.BuilderRunConfig(
                arch=state.Arch.ARM64,
                base=state.BaseImage.JAMMY,
                cloud_config=state.OpenstackCloudsConfig(
                    clouds={
                        state.UPLOAD_CLOUD_NAME: state._CloudsConfig(auth=None, region_name="test")
                    }
                ),
                external_build_config=None,
                num_revisions=1,
                runner_version="test",
            ),
            False,
            id="waiting integration data",
        ),
        pytest.param(
            state.BuilderRunConfig(
                arch=state.Arch.ARM64,
                base=state.BaseImage.JAMMY,
                cloud_config=state.OpenstackCloudsConfig(
                    clouds={
                        state.UPLOAD_CLOUD_NAME: state._CloudsConfig(
                            auth=state._CloudsAuthConfig(auth_url="test-auth-url"),
                            region_name="test",
                        )
                    }
                ),
                external_build_config=None,
                num_revisions=1,
                runner_version="test",
            ),
            True,
            id="integration ready",
        ),
    ],
)
def test__is_image_relation_ready_set_status(
    charm: GithubRunnerImageBuilderCharm,
    config: state.BuilderRunConfig,
    expected_return: bool,
):
    """
    arrange: given builder run config state.
    act: when _is_image_relation_ready_set_status is called.
    assert: expected boolean value is returned.
    """
    assert charm._is_image_relation_ready_set_status(config=config) == expected_return
