# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for charm module."""
import secrets

# We're monkeypatching the subprocess module for testing
import subprocess  # nosec: B404
from unittest.mock import MagicMock

import ops
import pytest
from ops import RelationChangedEvent

import builder
import charm as charm_module
import image
import proxy
import state
from app.src.github_runner_image_builder.logging import LOG_FILE_PATH
from charm import GithubRunnerImageBuilderCharm

# Need access to protected functions for testing
# pylint:disable=protected-access


@pytest.fixture(name="mock_builder")
def mock_builder_fixture(monkeypatch: pytest.MonkeyPatch):
    """Mock builder functions to avoid actual image building."""
    image_config = state.ImageConfig(
        arch=state.Arch.ARM64,
        bases=(state.BaseImage.FOCAL,),
        runner_version="",
        script_url=None,
        script_secrets=dict(),
    )
    monkeypatch.setattr(
        state.BuilderConfig,
        "from_charm",
        MagicMock(return_value=MagicMock(image_config=image_config)),
    )
    monkeypatch.setattr(builder, "install_clouds_yaml", MagicMock())
    monkeypatch.setattr(builder, "get_latest_images", MagicMock(return_value=[]))
    monkeypatch.setattr(builder, "run", MagicMock())
    monkeypatch.setattr(builder, "configure_cron", MagicMock(return_value=True))


@pytest.mark.parametrize(
    "hook",
    [
        pytest.param("_on_config_changed", id="config_changed"),
        pytest.param("_on_run_action", id="run_action"),
        pytest.param("_on_run", id="run event"),
    ],
)
def test_block_on_image_relation_not_ready(charm: GithubRunnerImageBuilderCharm, hook: str):
    """
    arrange: given hooks that should not run build when image relation is not yet ready.
    act: when the hook is called.
    assert: the charm falls into BlockedStatus.
    """
    getattr(charm, hook)(MagicMock())

    assert charm.unit.status == ops.BlockedStatus(f"{state.IMAGE_RELATION} integration required.")


@pytest.mark.usefixtures("mock_builder")
@pytest.mark.parametrize(
    "hook",
    [
        pytest.param("_on_config_changed", id="config_changed"),
        pytest.param("_on_run_action", id="run_action"),
        pytest.param("_on_run", id="run event"),
    ],
)
def test_hooks_that_trigger_run_for_all_clouds(
    monkeypatch: pytest.MonkeyPatch, charm: GithubRunnerImageBuilderCharm, hook: str
):
    """
    arrange: given hooks that should run build for all clouds when there is image relation data.
    act: when the hook is called.
    assert: the charm falls into ActiveStatus
    """
    monkeypatch.setattr(proxy, "configure_aproxy", MagicMock())

    getattr(charm, hook)(MagicMock())

    builder.run.assert_called_once()
    assert charm.unit.status == ops.ActiveStatus()


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
        state.BuilderConfig,
        "from_charm",
        MagicMock(side_effect=state.CharmConfigInvalidError("Invalid config")),
    )

    getattr(charm, hook)(MagicMock())

    assert charm.unit.status == ops.BlockedStatus("Invalid config")


@pytest.mark.parametrize(
    "hook,expected_active_msg",
    [
        pytest.param("_on_install", "Waiting for first image.", id="_on_install"),
        pytest.param("_on_upgrade_charm", "", id="_on_upgrade_charm"),
    ],
)
def test_installation(
    monkeypatch: pytest.MonkeyPatch,
    charm: GithubRunnerImageBuilderCharm,
    hook: str,
    expected_active_msg: str,
):
    """
    arrange: given a monekypatched setup_builder and setup_logrotate function.
    act: when _on_install is called.
    assert: setup_builder is called.
    """
    monkeypatch.setattr(state.BuilderConfig, "from_charm", MagicMock())
    monkeypatch.setattr(image, "Observer", MagicMock())
    monkeypatch.setattr(proxy, "setup", MagicMock())
    monkeypatch.setattr(builder, "initialize", (builder_setup_mock := MagicMock()))
    charm._setup_logrotate = (logrotate_setup_mock := MagicMock())

    getattr(charm, hook)(MagicMock())

    builder_setup_mock.assert_called_once()
    logrotate_setup_mock.assert_called_once()
    assert charm.unit.status == ops.ActiveStatus(expected_active_msg)


@pytest.mark.usefixtures("mock_builder")
def test__on_image_relation_changed(
    monkeypatch: pytest.MonkeyPatch, charm: GithubRunnerImageBuilderCharm
):
    """
    arrange: given monkeypatched builder with get_latest_images returning an empty list.
    act: when _on_image_relation_changed is called.
    assert: charm is in active status and run for the particular related unit is called.
    """
    monkeypatch.setattr(proxy, "configure_aproxy", MagicMock())
    charm.image_observer = MagicMock()
    fake_clouds_auth_config = state.CloudsAuthConfig(
        auth_url="http://example.com",
        username="user",
        password="pass",  # nosec no real password
        project_name="project_name",
        project_domain_name="project_domain_name",
        user_domain_name="user_domain_name",
    )
    monkeypatch.setattr(
        state.CloudsAuthConfig,
        "from_unit_relation_data",
        MagicMock(return_value=fake_clouds_auth_config),
    )
    builder.get_latest_images.return_value = []

    charm._on_image_relation_changed(MagicMock())

    assert charm.unit.status == ops.ActiveStatus()
    builder.run.assert_called_once()
    assert builder.run.call_args[1]["static_config"].cloud_config.upload_clouds == [
        fake_clouds_auth_config.get_id()
    ]


@pytest.mark.usefixtures("mock_builder")
def test__on_image_relation_changed_image_already_in_cloud(
    monkeypatch: pytest.MonkeyPatch, charm: GithubRunnerImageBuilderCharm
):
    """
    arrange: given monkeypatched builder with get_latest_image_id returning a list with one image.
    act: when _on_image_relation_changed is called.
    assert: charm is in active status and no run is triggered but image data is updated
    """
    monkeypatch.setattr(proxy, "configure_aproxy", MagicMock())
    charm.image_observer = MagicMock()
    fake_clouds_auth_config = state.CloudsAuthConfig(
        auth_url="http://example.com",
        username="user",
        password=secrets.token_hex(16),
        project_name="project_name",
        project_domain_name="project_domain_name",
        user_domain_name="user_domain_name",
    )
    monkeypatch.setattr(
        state.CloudsAuthConfig,
        "from_unit_relation_data",
        MagicMock(return_value=fake_clouds_auth_config),
    )
    cloud_image = builder.CloudImage(
        arch=state.Arch.X64, base=state.BaseImage.NOBLE, cloud_id="demo_demo", image_id=""
    )
    builder.get_latest_images.return_value = [cloud_image]

    charm._on_image_relation_changed(MagicMock())

    assert charm.unit.status == ops.ActiveStatus()
    assert builder.run.call_count == 0
    charm.image_observer.update_image_data.assert_called_with([[cloud_image]])


@pytest.mark.usefixtures("mock_builder")
@pytest.mark.parametrize(
    "with_unit",
    [
        pytest.param(True, id="with unit"),
        pytest.param(False, id="without unit"),
    ],
)
def test__on_image_relation_changed_no_unit_auth_data(
    monkeypatch: pytest.MonkeyPatch, charm: GithubRunnerImageBuilderCharm, with_unit: bool
):
    """
    arrange: given a situation where image related change has no unit or no auth data.
    act: when _on_image_relation_changed is called.
    assert: charm is not building image
    """
    monkeypatch.setattr(proxy, "configure_aproxy", MagicMock())
    charm.image_observer = MagicMock()

    monkeypatch.setattr(
        state.CloudsAuthConfig, "from_unit_relation_data", MagicMock(return_value=None)
    )

    evt = MagicMock(spec=RelationChangedEvent)
    evt.relation = MagicMock()

    if with_unit:
        evt.unit = MagicMock()
        evt.unit.name = "test/unit"
        evt.relation.data[evt.unit] = {
            "auth_url": "http://example.com",
            "username": "user",
            "password": "pass",
            "project_name": "project_name",
            "project_domain_name": "project_domain_name",
            "user_domain_name": "user_domain_name",
        }
    else:
        evt.unit = None

    charm._on_image_relation_changed(evt)

    builder.run.assert_not_called()


def test__setup_logrotate_error(
    monkeypatch, tmp_path, charm: GithubRunnerImageBuilderCharm, caplog
):
    """
    arrange: given monkeypatched logrotate path and subprocess call which raises an error.
    act: when _setup_logrotate is called.
    assert: configuration file is written and logrotate is called with debug flag.
    """
    monkeypatch.setattr(charm_module, "APP_LOGROTATE_CONFIG_PATH", (tmp_path / "logrotate.conf"))
    monkeypatch.setattr(
        subprocess,
        "check_call",
        (
            MagicMock(
                side_effect=subprocess.CalledProcessError(
                    returncode=1, cmd=["test"], output="", stderr="failure"
                )
            )
        ),
    )

    charm._setup_logrotate()

    assert any("Failed to set up logrotate" in message for message in caplog.messages)


def test__setup_logrotate(monkeypatch, tmp_path, charm: GithubRunnerImageBuilderCharm):
    """
    arrange: given monkeypatched logrotate path and subprocess call.
    act: when _setup_logrotate is called.
    assert: configuration file is written and logrotate is called with debug flag.
    """
    monkeypatch.setattr(
        charm_module, "APP_LOGROTATE_CONFIG_PATH", (logrotate_path := tmp_path / "logrotate.conf")
    )
    monkeypatch.setattr(subprocess, "check_call", (mock_check_call := MagicMock()))

    charm._setup_logrotate()

    logrotate_config = logrotate_path.read_text(encoding="utf-8")
    assert str(LOG_FILE_PATH) in logrotate_config
    mock_check_call.assert_called_once_with(
        ["/usr/sbin/logrotate", str(logrotate_path), "--debug"]
    )
