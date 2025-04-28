# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for charm module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

from unittest.mock import MagicMock

import ops
import pytest
from ops import RelationChangedEvent

import builder
import image
import proxy
import state
from charm import GithubRunnerImageBuilderCharm


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
    arrange: given a monekypatched builder.setup_builder function.
    act: when _on_install is called.
    assert: setup_builder is called.
    """
    monkeypatch.setattr(state.BuilderConfig, "from_charm", MagicMock())
    monkeypatch.setattr(image, "Observer", MagicMock())
    monkeypatch.setattr(proxy, "setup", MagicMock())
    monkeypatch.setattr(builder, "initialize", (setup_mock := MagicMock()))

    getattr(charm, hook)(MagicMock())

    setup_mock.assert_called_once()
    assert charm.unit.status == ops.ActiveStatus(expected_active_msg)


@pytest.mark.usefixtures("mock_builder")
def test__on_image_relation_changed(
    monkeypatch: pytest.MonkeyPatch, charm: GithubRunnerImageBuilderCharm
):
    """
    arrange: given monkeypatched builder, openstack manager, image_observer.
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

    charm._on_image_relation_changed(MagicMock())

    assert charm.unit.status == ops.ActiveStatus()
    assert builder.run.call_args[1]["static_config"].cloud_config.upload_clouds == [
        fake_clouds_auth_config.get_id()
    ]


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
