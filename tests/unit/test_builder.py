# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for builder module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

import secrets

# The subprocess module is imported for monkeypatching.
import subprocess  # nosec: B404
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml
from charms.operator_libs_linux.v0 import apt

import builder
import state
from tests.unit import factories


def test_setup_builder_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched internal funcs that raises an error.
    act: when setup_builder is called.
    assert: BuilderSetupError is raised.
    """
    monkeypatch.setattr(
        builder,
        "_install_dependencies",
        MagicMock(side_effect=builder.DependencyInstallError("Failed to install dependencies.")),
    )

    with pytest.raises(builder.BuilderSetupError) as exc:
        builder.initialize(init_config=MagicMock())

    assert "Failed to install dependencies." in str(exc.getrepr())


def test_setup_builder(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched internal funcs.
    act: when setup_builder is called.
    assert: expected mocks are called.
    """
    monkeypatch.setattr(
        builder,
        "_install_dependencies",
        (deps_mock := MagicMock()),
    )
    monkeypatch.setattr(
        builder,
        "_initialize_image_builder",
        (image_mock := MagicMock()),
    )
    monkeypatch.setattr(
        builder,
        "install_clouds_yaml",
        (install_clouds_yaml_mock := MagicMock()),
    )
    monkeypatch.setattr(
        builder,
        "configure_cron",
        (configure_cron_mock := MagicMock()),
    )

    builder.initialize(init_config=MagicMock())

    deps_mock.assert_called_once()
    image_mock.assert_called_once()
    install_clouds_yaml_mock.assert_called_once()
    configure_cron_mock.assert_called_once()


def test__install_dependencies_fail(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: monkeypatched subprocess.run function.
    act: when _install_dependencies is called.
    assert: DependencyInstallError is raised.
    """
    monkeypatch.setattr(apt, "add_package", MagicMock())
    monkeypatch.setattr(
        subprocess,
        "run",
        MagicMock(side_effect=subprocess.CalledProcessError(1, [], "", "error installing deps")),
    )

    with pytest.raises(builder.DependencyInstallError) as exc:
        builder._install_dependencies(channel=MagicMock())

    assert "error installing deps" in str(exc.getrepr())


def test__install_dependencies(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: monkeypatched apt.add_package function.
    act: when _install_dependencies is called.
    assert: mocked functions are called.
    """
    monkeypatch.setattr(apt, "add_package", (apt_mock := MagicMock()))
    monkeypatch.setattr(subprocess, "run", (run_mock := MagicMock()))

    builder._install_dependencies(channel=MagicMock())

    apt_mock.assert_called_once()
    run_mock.assert_called_once()


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(
            subprocess.CalledProcessError(1, [], "", "error running image builder install"),
            id="process error",
        ),
        pytest.param(
            subprocess.SubprocessError("Something happened"),
            id="general error",
        ),
    ],
)
def test__initialize_image_builder_error(
    monkeypatch: pytest.MonkeyPatch,
    error: subprocess.CalledProcessError | subprocess.SubprocessError,
):
    """
    arrange: given monkeypatched subprocess.run function that raises an error.
    act: when _initialize_image_builder is called.
    assert: ImageBuilderInstallError is raised.
    """
    monkeypatch.setattr(subprocess, "run", MagicMock(side_effect=error))

    with pytest.raises(builder.ImageBuilderInitializeError):
        builder._initialize_image_builder(init_config=MagicMock())


@pytest.mark.parametrize(
    "external_build",
    [
        pytest.param(True, id="external build"),
        pytest.param(False, id="chroot build"),
    ],
)
def test__initialize_image_builder(monkeypatch: pytest.MonkeyPatch, external_build: bool):
    """
    arrange: given monkeypatched subprocess.run function.
    act: when _initialize_image_builder is called.
    assert: No errors are raised.
    """
    monkeypatch.setattr(subprocess, "run", MagicMock())
    init_config_mock = MagicMock()
    init_config_mock.external_build = external_build

    builder._initialize_image_builder(init_config=init_config_mock)


def test_install_clouds_yaml_not_exists(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """
    arrange: given mocked empty OPENSTACK_CLOUDS_YAML_PATH.
    act: when install_clouds_yaml is called.
    assert: contents of cloud_config are written.
    """
    test_path = tmp_path / "not-exists"
    monkeypatch.setattr(builder, "OPENSTACK_CLOUDS_YAML_PATH", test_path)

    builder.install_clouds_yaml(
        cloud_config=state.OpenstackCloudsConfig(
            clouds={
                "test": state._CloudsConfig(
                    auth=state.CloudsAuthConfig(
                        auth_url="test-url",
                        password=(test_password := secrets.token_hex(16)),
                        project_domain_name="test_domain",
                        project_name="test-project",
                        user_domain_name="test_domain",
                        username="test-user",
                    )
                )
            }
        )
    )

    contents = test_path.read_text(encoding="utf-8")
    assert (
        contents
        == f"""clouds:
  test:
    auth:
      auth_url: test-url
      password: {test_password}
      project_domain_name: test_domain
      project_name: test-project
      user_domain_name: test_domain
      username: test-user
"""
    )


@pytest.mark.parametrize(
    "original_contents, cloud_config",
    [
        pytest.param(
            "",
            state.OpenstackCloudsConfig(
                clouds={"test": state._CloudsConfig(auth=factories.CloudAuthFactory())}
            ),
            id="changed",
        ),
        pytest.param(
            """{
    'clouds': {
        'test': {
            'auth': {
                'auth_url': 'test-auth-url',
                'password': 'test-password',
                'project_domain_name': 'test-project-domain',
                'project_name': 'test-project-name',
                'user_domain_name': 'test-user-domain',
                'username': 'test-username',
            },
        },
    },
}""",
            state.OpenstackCloudsConfig(
                clouds={"test": state._CloudsConfig(auth=factories.CloudAuthFactory())}
            ),
            id="not changed",
        ),
    ],
)
def test_install_clouds_yaml(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    original_contents: str,
    cloud_config: state.OpenstackCloudsConfig,
):
    """
    arrange: given mocked empty OPENSTACK_CLOUDS_YAML_PATH.
    act: when install_clouds_yaml is called.
    assert: contents of cloud_config are written.
    """
    test_path = tmp_path / "exists"
    test_path.write_text(original_contents, encoding="utf-8")
    monkeypatch.setattr(builder, "OPENSTACK_CLOUDS_YAML_PATH", test_path)

    builder.install_clouds_yaml(cloud_config=cloud_config)

    contents = yaml.safe_load(test_path.read_text(encoding="utf-8"))
    assert contents == cloud_config.model_dump()


def test_configure_cron_no_reconfigure(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched _should_configure_cron which returns False, denoting no change.
    act: when configure_cron is called.
    assert: cron service is not restarted.
    """
    monkeypatch.setattr(builder, "_should_configure_cron", MagicMock(return_value=False))
    monkeypatch.setattr(builder.systemd, "service_restart", (service_restart_mock := MagicMock()))

    builder.configure_cron(
        unit_name=MagicMock(),
        interval=1,
    )

    service_restart_mock.assert_not_called()


@pytest.mark.parametrize(
    "expected_file_contents",
    [
        pytest.param(
            """0 */1 * * * ubuntu /usr/bin/run-one /usr/bin/bash -c \
/usr/bin/juju-exec "test-unit-name" "JUJU_DISPATCH_PATH=run HOME=/home/ubuntu ./dispatch"\
""",
            id="runner version set",
        ),
    ],
)
def test_configure_cron(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    expected_file_contents: str,
):
    """
    arrange: given monkeypatched subfunctions of configure_cron.
    act: when configure_cron is called.
    assert: subfunctions are called and cron file is written with expected contents.
    """
    monkeypatch.setattr(builder, "_should_configure_cron", MagicMock())
    monkeypatch.setattr(builder.systemd, "service_restart", (service_restart_mock := MagicMock()))
    test_path = tmp_path / "test"
    monkeypatch.setattr(builder, "CRON_BUILD_SCHEDULE_PATH", test_path)
    test_interval = 1

    builder.configure_cron(unit_name="test-unit-name", interval=test_interval)

    service_restart_mock.assert_called_once()
    cron_contents = test_path.read_text(encoding="utf-8")
    assert cron_contents == expected_file_contents.format(TEST_PATH=test_path)


def test__should_configure_cron_no_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """
    arrange: given a monkeypatched CRON_BUILD_SCHEDULE_PATH that does not exist.
    act: when _should_configure_cron is called.
    assert: Truthy value is returned.
    """
    test_path = tmp_path / "not-exists"
    monkeypatch.setattr(builder, "CRON_BUILD_SCHEDULE_PATH", test_path)

    assert builder._should_configure_cron(cron_contents=MagicMock())


def test__should_configure_cron(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """
    arrange: given _should_configure_cron input values and monkeypatched CRON_BUILD_SCHEDULE_PATH.
    act: when _should_configure_cron is called.
    assert: expected value is returned.
    """
    test_path = tmp_path / "test"
    test_path.write_text("test contents\n", encoding="utf-8")
    monkeypatch.setattr(builder, "CRON_BUILD_SCHEDULE_PATH", test_path)

    assert builder._should_configure_cron(cron_contents="mismatching contents\n")


def test_run_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched pool.map that raises an error.
    act: when run is called.
    assert: BuilderRunError is raised.
    """
    monkeypatch.setattr(builder.multiprocessing, "Pool", pool_context_mock := MagicMock())
    pool_context_mock.return_value.__enter__.return_value = (pool_mock := MagicMock())
    pool_mock.map = MagicMock(side_effect=builder.multiprocessing.ProcessError("Process Error"))
    with pytest.raises(builder.BuilderRunError):
        builder.run(config=MagicMock(), proxy=None)


def _patched_test_func(*_args, **_kwargs):
    """Patch function.

    Args:
        _args: args placeholder.
        _kwargs: keyword args placeholder

    Returns:
        "test" string
    """
    return "test"


def test_run(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched _run function.
    act: when run is called.
    assert: run build results are returned.
    """
    monkeypatch.setattr(builder, "_parametrize_build", MagicMock(return_value=["test", "test"]))
    monkeypatch.setattr(builder, "_run", _patched_test_func)

    assert ["test", "test"] == builder.run(
        config=state.BuilderRunConfig(
            arch=state.Arch.ARM64,
            bases=(state.BaseImage.JAMMY, state.BaseImage.NOBLE),
            cloud_config=state.OpenstackCloudsConfig(clouds={}),
            external_build_config=None,
            num_revisions=1,
            prefix="app-name",
            runner_version="",
        ),
        proxy=None,
    )


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(
            MagicMock(side_effect=subprocess.SubprocessError("Failed to spawn process")),
            id="general subprocess error",
        ),
        pytest.param(
            MagicMock(
                side_effect=subprocess.CalledProcessError(
                    returncode=1,
                    cmd=["test"],
                    output="Failed to spawn process",
                    stderr="Failed to spawn process",
                )
            ),
            id="called process error",
        ),
    ],
)
def test__run_error(
    monkeypatch: pytest.MonkeyPatch,
    error: subprocess.SubprocessError | subprocess.CalledProcessError,
):
    """
    arrange: given a monkeypatched subprocess Popen that raises an error.
    act: when _run is called.
    assert: BuilderRunError is raised.
    """
    monkeypatch.setattr(builder.subprocess, "check_output", error)

    with pytest.raises(builder.BuilderRunError):
        builder._run(config=MagicMock())


@pytest.mark.parametrize(
    "run_config",
    [
        pytest.param(
            builder.RunConfig(
                image=builder._RunImageConfig(
                    arch=state.Arch.ARM64,
                    base=state.BaseImage.JAMMY,
                    runner_version="1.2.3",
                    prefix="app-name",
                ),
                cloud=builder._RunCloudConfig(
                    build_cloud="test",
                    build_flavor="test",
                    build_network="test",
                    upload_clouds=["test"],
                    resource_prefix="app-name",
                    num_revisions=1,
                    proxy=None,
                ),
            ),
            id="runner version config set",
        ),
        pytest.param(
            builder.RunConfig(
                image=builder._RunImageConfig(
                    arch=state.Arch.ARM64,
                    base=state.BaseImage.JAMMY,
                    runner_version=None,
                    prefix="app-name",
                ),
                cloud=builder._RunCloudConfig(
                    build_cloud="test",
                    build_flavor="test",
                    build_network="test",
                    upload_clouds=["test"],
                    resource_prefix="app-name",
                    num_revisions=1,
                    proxy="test",
                ),
            ),
            id="proxy config set",
        ),
    ],
)
def test__run(monkeypatch: pytest.MonkeyPatch, run_config: builder.RunConfig):
    """
    arrange: given a monkeypatched subprocess call.
    act: when _run is called.
    assert: the call to image builder is made.
    """
    monkeypatch.setattr(
        builder.subprocess,
        "check_output",
        check_output_mock := MagicMock(return_value="Image build success\ntest-image-id"),
    )

    builder._run(config=run_config)

    check_output_mock.assert_called_once()


def test_get_latest_images_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched pool.map that raises an error.
    act: when get_latest_images is called.
    assert: GetLatestImageError is raised.
    """
    monkeypatch.setattr(builder.multiprocessing, "Pool", pool_context_mock := MagicMock())
    pool_context_mock.return_value.__enter__.return_value = (pool_mock := MagicMock())
    pool_mock.map = MagicMock(side_effect=builder.multiprocessing.ProcessError("Process Error"))
    with pytest.raises(builder.GetLatestImageError):
        builder.get_latest_images(config=MagicMock(), cloud_id="test")


def test_get_latest_images(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched _run function.
    act: when get_latest_images is called.
    assert: get_latest_images results are returned.
    """
    monkeypatch.setattr(builder, "_parametrize_fetch", MagicMock(return_value=["test", "test"]))
    monkeypatch.setattr(builder, "_get_latest_image", _patched_test_func)

    assert ["test", "test"] == builder.get_latest_images(
        config=state.BuilderRunConfig(
            arch=state.Arch.ARM64,
            bases=(state.BaseImage.JAMMY, state.BaseImage.NOBLE),
            cloud_config=state.OpenstackCloudsConfig(clouds={}),
            external_build_config=None,
            num_revisions=1,
            prefix="app-name",
            runner_version="",
        ),
        cloud_id="test",
    )


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(
            subprocess.CalledProcessError(1, [], "", "error running image builder install"),
            id="process error",
        ),
        pytest.param(
            subprocess.SubprocessError("Something happened"),
            id="general error",
        ),
    ],
)
def test__get_latest_image_error(
    monkeypatch: pytest.MonkeyPatch,
    error: subprocess.CalledProcessError | subprocess.SubprocessError,
):
    """
    arrange: given monkeypatched subprocess.run that raises an error.
    act: when _get_latest_image is called.
    assert: GetLatestImageError is raised.
    """
    monkeypatch.setattr(subprocess, "check_output", MagicMock(side_effect=error))

    with pytest.raises(builder.GetLatestImageError):
        builder._get_latest_image(config=MagicMock())


def test__get_latest_image(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched subprocess.check_output that returns an image_id.
    act: when _get_latest_image is called.
    assert: expected CloudImage is returned.
    """
    monkeypatch.setattr(subprocess, "check_output", MagicMock(return_value="test-image"))

    assert builder._get_latest_image(
        config=builder.FetchConfig(
            arch=state.Arch.ARM64,
            base=state.BaseImage.JAMMY,
            cloud_id="test-cloud",
            prefix="app-name",
        )
    ) == builder.CloudImage(
        arch=state.Arch.ARM64,
        base=state.BaseImage.JAMMY,
        cloud_id="test-cloud",
        image_id="test-image",
    )


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(
            subprocess.CalledProcessError(1, [], "", "error running image builder install"),
            id="process error",
        ),
        pytest.param(
            subprocess.SubprocessError("Something happened"),
            id="general error",
        ),
    ],
)
def test_upgrade_app_error(
    monkeypatch: pytest.MonkeyPatch,
    error: subprocess.CalledProcessError | subprocess.SubprocessError,
):
    """
    arrange: given monkeypatched subprocess.run that raises an error.
    act: when upgrade_app is called.
    assert: UpgradeApplicationError is raised.
    """
    monkeypatch.setattr(subprocess, "run", MagicMock(side_effect=error))

    with pytest.raises(builder.UpgradeApplicationError):
        builder.upgrade_app()
