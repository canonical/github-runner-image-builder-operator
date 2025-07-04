# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for builder module."""

# Need access to protected functions for testing.
# We are testing extensively with data structures, hence the many lines.
# pylint:disable=protected-access, too-many-lines

import secrets

# The subprocess module is imported for monkeypatching.
import subprocess  # nosec: B404
import typing
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml
from charms.operator_libs_linux.v0 import apt

import builder
import pipx
import state
from exceptions import PipXError
from tests.unit import factories

TEST_STATIC_CONFIG: builder.StaticConfigs = factories.StaticConfigFactory.create()
TEST_RUN_CONFIG: builder.RunConfig = factories.RunConfigFactory.create()


def test_initialize_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched internal funcs that raises an error.
    act: when initialize is called.
    assert: BuilderInitError is raised.
    """
    monkeypatch.setattr(builder, "install_clouds_yaml", MagicMock())
    monkeypatch.setattr(
        builder,
        "_install_dependencies",
        MagicMock(side_effect=builder.DependencyInstallError("Failed to install dependencies.")),
    )

    with pytest.raises(builder.BuilderInitError) as exc:
        builder.initialize(app_init_config=MagicMock())

    assert "Failed to install dependencies." in str(exc.getrepr())


def test_initialize(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """
    arrange: given monkeypatched functions calling external dependencies.
    act: when initialize is called.
    assert: clouds.yaml file is written.
    """
    test_clouds_yaml_path = tmp_path / "clouds.yaml"
    monkeypatch.setattr(builder, "_install_dependencies", MagicMock())
    monkeypatch.setattr(builder, "_initialize_image_builder", MagicMock())
    monkeypatch.setattr(builder, "configure_cron", MagicMock())
    monkeypatch.setattr(builder, "OPENSTACK_CLOUDS_YAML_PATH", test_clouds_yaml_path)

    builder.initialize(
        app_init_config=builder.ApplicationInitializationConfig(
            cloud_config=factories.StateCloudConfigFactory(),
            cron_interval=MagicMock(),
            image_arch=MagicMock(),
            resource_prefix=MagicMock(),
            unit_name=MagicMock(),
        )
    )

    assert test_clouds_yaml_path.exists()


@pytest.mark.parametrize(
    "apt_mock,pipx_install_mock",
    [
        pytest.param(
            MagicMock(side_effect=apt.PackageNotFoundError("package not found")),
            MagicMock(),
            id="apt error",
        ),
        pytest.param(
            MagicMock(),
            MagicMock(side_effect=builder.PipXError("error installing deps")),
            id="pipx install error",
        ),
    ],
)
def test__install_dependencies_fail(
    apt_mock: MagicMock, pipx_install_mock, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: monkeypatched subprocess.run function.
    act: when _install_dependencies is called.
    assert: DependencyInstallError is raised.
    """
    monkeypatch.setattr(apt, "add_package", apt_mock)
    monkeypatch.setattr(pipx, "uninstall", MagicMock())
    monkeypatch.setattr(pipx, "install", pipx_install_mock)

    with pytest.raises(builder.DependencyInstallError) as exc:
        builder._install_dependencies()

    assert exc.value.__cause__ == (apt_mock.side_effect or pipx_install_mock.side_effect)


def test__install_dependencies(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: monkeypatched apt.add_package function.
    act: when _install_dependencies is called.
    assert: mocked functions are called.
    """
    monkeypatch.setattr(apt, "add_package", (apt_mock := MagicMock()))
    monkeypatch.setattr(pipx, "uninstall", (pipx_uninstall_mock := MagicMock()))
    monkeypatch.setattr(pipx, "install", (pipx_install_mock := MagicMock()))

    builder._install_dependencies()

    apt_mock.assert_called_once()
    pipx_uninstall_mock.assert_called_once()
    pipx_install_mock.assert_called_once()


def test__install_dependencies_uninstalling_app_fail(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """
    arrange: given monkeypatched pipx.uninstall function that raises an error.
    act: when _install_dependencies is called.
    assert: the error is ignored and an information is logged.
    """
    monkeypatch.setattr(apt, "add_package", (apt_mock := MagicMock()))
    monkeypatch.setattr(
        pipx,
        "uninstall",
        (pipx_uninstall_mock := MagicMock(side_effect=PipXError("error uninstalling deps"))),
    )
    monkeypatch.setattr(pipx, "install", (pipx_install_mock := MagicMock()))

    builder._install_dependencies()

    apt_mock.assert_called_once()
    pipx_uninstall_mock.assert_called_once()
    pipx_install_mock.assert_called_once()

    assert "error uninstalling deps" in " ".join(caplog.messages)


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
    monkeypatch.setattr(builder, "_build_init_command", MagicMock(return_value=[]))
    monkeypatch.setattr(subprocess, "run", MagicMock(side_effect=error))

    with pytest.raises(builder.ImageBuilderInitializeError):
        builder._initialize_image_builder(
            cloud_name=MagicMock(), image_arch=MagicMock(), resource_prefix=MagicMock()
        )


@pytest.mark.parametrize(
    "resource_prefix, expected_command",
    [
        pytest.param(
            None,
            [
                "/usr/bin/sudo",
                "/home/ubuntu/.local/bin/github-runner-image-builder",
                "--os-cloud",
                "test-cloud-name",
                "init",
                "--arch",
                "arm64",
            ],
            id="no resource prefix",
        ),
        pytest.param(
            "test-prefix",
            [
                "/usr/bin/sudo",
                "/home/ubuntu/.local/bin/github-runner-image-builder",
                "--os-cloud",
                "test-cloud-name",
                "init",
                "--arch",
                "arm64",
                "--prefix",
                "test-prefix",
            ],
            id="test resource prefix",
        ),
    ],
)
def test__build_init_command(resource_prefix: str | None, expected_command: list[str]):
    """
    arrange: given application init command arguments and options.
    act: when _build_init_command is called.
    assert: expected CLI command line is constructed.
    """
    assert (
        builder._build_init_command(
            cloud_name="test-cloud-name",
            image_arch=state.Arch.ARM64,
            resource_prefix=resource_prefix,
        )
        == expected_command
    )


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


def test_install_clouds_yaml_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """
    arrange: given mocked OPENSTACK_CLOUDS_YAML_PATH with unchanged contents.
    act: when install_clouds_yaml is called.
    assert: contents of cloud_config are written.
    """
    test_path = tmp_path / "test_yaml"
    test_config = state.OpenstackCloudsConfig(
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
    test_path.write_text(
        yaml.dump(test_config.model_dump()),
        encoding="utf-8",
    )
    monkeypatch.setattr(builder, "OPENSTACK_CLOUDS_YAML_PATH", test_path)

    builder.install_clouds_yaml(cloud_config=test_config)

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
            """0 */1 * * * root /usr/bin/run-one /usr/bin/bash -c \
'/usr/bin/juju-exec "test-unit-name" "JUJU_DISPATCH_PATH=run HOME=/home/ubuntu ./dispatch"'
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
        builder.run(config_matrix=MagicMock(), static_config=MagicMock())


def _patched__get_latest_image(*args, **_kwargs):
    """Patch the fct _get_ltest image.

    We use a function because of pickling issues with multiprocessing.

    If first arg is "empty-image" the returned CloudImage object has an empty image_id.
    Args:
        args: args placeholder.
        _kwargs: keyword args placeholder

    Returns:
        "test" string
    """
    if args[0] == "empty-image":
        # Simulating a case where the image has an empty ID.
        return builder.CloudImage(
            arch=state.Arch.X64, base=state.BaseImage.NOBLE, cloud_id=args[0], image_id=""
        )
    return builder.CloudImage(
        arch=state.Arch.X64, base=state.BaseImage.NOBLE, cloud_id=args[0], image_id="test_id"
    )


def test_run(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched _run function.
    act: when run is called.
    assert: run build results are returned.
    """
    monkeypatch.setattr(builder, "_parametrize_build", MagicMock(return_value=["test1", "test2"]))
    monkeypatch.setattr(builder, "_run", _patched__get_latest_image)

    assert [
        builder.CloudImage(
            arch=state.Arch.X64, base=state.BaseImage.NOBLE, cloud_id=cloud_id, image_id="test_id"
        )
        for cloud_id in ["test1", "test2"]
    ] == builder.run(config_matrix=MagicMock(), static_config=MagicMock())


# pylint doesn't quite understand walrus operators
# pylint: disable=unused-variable,undefined-variable
@pytest.mark.parametrize(
    "config_matrix, expected_configs",
    [
        pytest.param(
            builder.ConfigMatrix(
                bases=(state.BaseImage.FOCAL, state.BaseImage.JAMMY, state.BaseImage.NOBLE),
            ),
            (
                builder.RunConfig(
                    image=builder.ImageConfig(
                        arch=TEST_STATIC_CONFIG.image_config.arch,
                        base=state.BaseImage.FOCAL,
                        prefix=TEST_STATIC_CONFIG.cloud_config.resource_prefix,
                        script_config=builder.ScriptConfig(
                            script_url="https://test-url.com/script.sh",
                            script_secrets={"test_secret": "test_value"},
                        ),
                        runner_version="1.2.3",
                    ),
                    cloud=builder.CloudConfig(
                        build_cloud=TEST_STATIC_CONFIG.cloud_config.build_cloud,
                        build_flavor=TEST_STATIC_CONFIG.cloud_config.build_flavor,
                        build_network=TEST_STATIC_CONFIG.cloud_config.build_network,
                        resource_prefix=TEST_STATIC_CONFIG.cloud_config.resource_prefix,
                        num_revisions=TEST_STATIC_CONFIG.cloud_config.num_revisions,
                        upload_clouds=TEST_STATIC_CONFIG.cloud_config.upload_clouds,
                    ),
                    external_service=builder.ExternalServiceConfig(
                        proxy=TEST_STATIC_CONFIG.service_config.proxy,
                    ),
                ),
                builder.RunConfig(
                    image=builder.ImageConfig(
                        arch=TEST_STATIC_CONFIG.image_config.arch,
                        base=state.BaseImage.JAMMY,
                        prefix=TEST_STATIC_CONFIG.cloud_config.resource_prefix,
                        script_config=builder.ScriptConfig(
                            script_url="https://test-url.com/script.sh",
                            script_secrets={"test_secret": "test_value"},
                        ),
                        runner_version="1.2.3",
                    ),
                    cloud=builder.CloudConfig(
                        build_cloud=TEST_STATIC_CONFIG.cloud_config.build_cloud,
                        build_flavor=TEST_STATIC_CONFIG.cloud_config.build_flavor,
                        build_network=TEST_STATIC_CONFIG.cloud_config.build_network,
                        resource_prefix=TEST_STATIC_CONFIG.cloud_config.resource_prefix,
                        num_revisions=TEST_STATIC_CONFIG.cloud_config.num_revisions,
                        upload_clouds=TEST_STATIC_CONFIG.cloud_config.upload_clouds,
                    ),
                    external_service=builder.ExternalServiceConfig(
                        proxy=TEST_STATIC_CONFIG.service_config.proxy,
                    ),
                ),
                builder.RunConfig(
                    image=builder.ImageConfig(
                        arch=TEST_STATIC_CONFIG.image_config.arch,
                        base=state.BaseImage.NOBLE,
                        prefix=TEST_STATIC_CONFIG.cloud_config.resource_prefix,
                        script_config=builder.ScriptConfig(
                            script_url="https://test-url.com/script.sh",
                            script_secrets={"test_secret": "test_value"},
                        ),
                        runner_version="1.2.3",
                    ),
                    cloud=builder.CloudConfig(
                        build_cloud=TEST_STATIC_CONFIG.cloud_config.build_cloud,
                        build_flavor=TEST_STATIC_CONFIG.cloud_config.build_flavor,
                        build_network=TEST_STATIC_CONFIG.cloud_config.build_network,
                        resource_prefix=TEST_STATIC_CONFIG.cloud_config.resource_prefix,
                        num_revisions=TEST_STATIC_CONFIG.cloud_config.num_revisions,
                        upload_clouds=TEST_STATIC_CONFIG.cloud_config.upload_clouds,
                    ),
                    external_service=builder.ExternalServiceConfig(
                        proxy=TEST_STATIC_CONFIG.service_config.proxy,
                    ),
                ),
            ),
            id="multiple OS bases",
        ),
    ],
)
def test__parametrize_build(
    config_matrix: builder.ConfigMatrix,
    expected_configs: tuple[builder.RunConfig, ...],
):
    """
    arrange: given configurable builder run configuration matrix.
    act: when _parametrize_build is called.
    assert: expected build configurations are returned.
    """
    assert (
        builder._parametrize_build(config_matrix=config_matrix, static_config=TEST_STATIC_CONFIG)
        == expected_configs
    )


# pylint: enable=unused-variable,undefined-variable


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
    "upload_clouds, output_image_ids, expected_cloud_images",
    [
        pytest.param(
            ("test-upload-cloud-a",),
            ("image-id-a",),
            [
                builder.CloudImage(
                    arch=TEST_RUN_CONFIG.image.arch,
                    base=TEST_RUN_CONFIG.image.base,
                    cloud_id="test-upload-cloud-a",
                    image_id="image-id-a",
                )
            ],
            id="single upload cloud",
        ),
        pytest.param(
            ("test-upload-cloud-a", "test-upload-cloud-b"),
            ("image-id-a", "image-id-b"),
            [
                builder.CloudImage(
                    arch=TEST_RUN_CONFIG.image.arch,
                    base=TEST_RUN_CONFIG.image.base,
                    cloud_id="test-upload-cloud-a",
                    image_id="image-id-a",
                ),
                builder.CloudImage(
                    arch=TEST_RUN_CONFIG.image.arch,
                    base=TEST_RUN_CONFIG.image.base,
                    cloud_id="test-upload-cloud-b",
                    image_id="image-id-b",
                ),
            ],
            id="multiple upload clouds",
        ),
    ],
)
def test__run(
    monkeypatch: pytest.MonkeyPatch,
    upload_clouds: typing.Iterable[str],
    output_image_ids: typing.Iterable[str],
    expected_cloud_images: list[builder.CloudImage],
):
    """
    arrange: given a monkeypatched subprocess call.
    act: when _run is called.
    assert: the call to image builder is made.
    """
    # Mock the image builder output.
    monkeypatch.setattr(
        builder.subprocess,
        "check_output",
        MagicMock(return_value=f"Image build success:\n{','.join(output_image_ids)}"),
    )
    test_run_config: builder.RunConfig = factories.RunConfigFactory.create()
    test_run_config.cloud.upload_clouds = upload_clouds

    assert builder._run(config=test_run_config) == expected_cloud_images


@pytest.mark.parametrize(
    "run_args, cloud_options, image_options, service_options, expected_command",
    [
        pytest.param(
            builder._RunArgs(cloud_name="test-build-cloud", image_name="test-output-image-name"),
            builder._CloudOptions(
                flavor=None, keep_revisions=None, network=None, prefix=None, upload_clouds=None
            ),
            builder._ImageOptions(
                arch=None,
                image_base=None,
                runner_version=None,
                script_url=None,
                script_secrets=None,
            ),
            builder._ServiceOptions(proxy=None),
            [
                "/usr/bin/run-one",
                "/usr/bin/sudo",
                "--preserve-env",
                "/home/ubuntu/.local/bin/github-runner-image-builder",
                "--os-cloud",
                "test-build-cloud",
                "run",
                "test-output-image-name",
            ],
            id="Run args only",
        ),
        pytest.param(
            builder._RunArgs(cloud_name="test-build-cloud", image_name="test-output-image-name"),
            builder._CloudOptions(
                flavor="test-flavor",
                keep_revisions=5,
                network="test-network",
                prefix="test-prefix-",
                upload_clouds=("test-upload-cloud-a", "test-upload-cloud-b"),
            ),
            builder._ImageOptions(
                arch=None,
                image_base=None,
                runner_version=None,
                script_url=None,
                script_secrets=None,
            ),
            builder._ServiceOptions(proxy=None),
            [
                "/usr/bin/run-one",
                "/usr/bin/sudo",
                "--preserve-env",
                "/home/ubuntu/.local/bin/github-runner-image-builder",
                "--os-cloud",
                "test-build-cloud",
                "run",
                "test-output-image-name",
                "--flavor",
                "test-flavor",
                "--keep-revisions",
                "5",
                "--network",
                "test-network",
                "--prefix",
                "test-prefix-",
                "--upload-clouds",
                "test-upload-cloud-a,test-upload-cloud-b",
            ],
            id="With cloud options",
        ),
        pytest.param(
            builder._RunArgs(cloud_name="test-build-cloud", image_name="test-output-image-name"),
            builder._CloudOptions(
                flavor=None, keep_revisions=None, network=None, prefix=None, upload_clouds=None
            ),
            builder._ImageOptions(
                arch=state.Arch.ARM64,
                image_base=state.BaseImage.JAMMY,
                runner_version="1.2.3",
                script_url="https://test-script-url.com/script.sh",
                script_secrets=None,
            ),
            builder._ServiceOptions(proxy=None),
            [
                "/usr/bin/run-one",
                "/usr/bin/sudo",
                "--preserve-env",
                "/home/ubuntu/.local/bin/github-runner-image-builder",
                "--os-cloud",
                "test-build-cloud",
                "run",
                "test-output-image-name",
                "--arch",
                "arm64",
                "--base-image",
                "jammy",
                "--runner-version",
                "1.2.3",
                "--script-url",
                "https://test-script-url.com/script.sh",
            ],
            id="With image options",
        ),
        pytest.param(
            builder._RunArgs(cloud_name="test-build-cloud", image_name="test-output-image-name"),
            builder._CloudOptions(
                flavor=None, keep_revisions=None, network=None, prefix=None, upload_clouds=None
            ),
            builder._ImageOptions(
                arch=None,
                image_base=None,
                runner_version=None,
                script_url=None,
                script_secrets=None,
            ),
            builder._ServiceOptions(
                proxy="https://test-proxy.com:3128",
            ),
            [
                "/usr/bin/run-one",
                "/usr/bin/sudo",
                "--preserve-env",
                "/home/ubuntu/.local/bin/github-runner-image-builder",
                "--os-cloud",
                "test-build-cloud",
                "run",
                "test-output-image-name",
                "--proxy",
                "test-proxy.com:3128",
            ],
            id="With service options",
        ),
    ],
)
def test__build_run_command(
    run_args: builder._RunArgs,
    cloud_options: builder._CloudOptions,
    image_options: builder._ImageOptions,
    service_options: builder._ServiceOptions,
    expected_command: list[str],
):
    """
    arrange: given CLI component options.
    act: when _build_run_command is called.
    assert: expected CLI call is built.
    """
    assert (
        builder._build_run_command(
            run_args=run_args,
            cloud_options=cloud_options,
            image_options=image_options,
            service_options=service_options,
        )
        == expected_command
    )


@pytest.mark.parametrize(
    "config, expected_name",
    [
        pytest.param(
            builder.ImageConfig(
                arch=state.Arch.ARM64,
                base=state.BaseImage.JAMMY,
                runner_version="",
                prefix="app-name",
                script_config=builder.ScriptConfig(script_url=None, script_secrets=None),
            ),
            "app-name-jammy-arm64",
            id="raw",
        ),
    ],
)
def test__run_image_config_image_name(config: builder.ImageConfig, expected_name: str):
    """
    arrange: given _RunImageConfig.
    act: when image_name property is accessed.
    assert: expected image names are returned.
    """
    assert config.image_name == expected_name


@pytest.mark.parametrize(
    "config, expected_name",
    [
        pytest.param(
            builder.FetchConfig(
                arch=state.Arch.ARM64,
                base=state.BaseImage.JAMMY,
                cloud_id="",
                prefix="app-name",
            ),
            "app-name-jammy-arm64",
            id="raw",
        ),
    ],
)
def test__fetch_config_image_name(config: builder.FetchConfig, expected_name: str):
    """
    arrange: given FetchConfig.
    act: when image_name property is accessed.
    assert: expected image names are returned.
    """
    assert config.image_name == expected_name


@pytest.mark.parametrize(
    "config_matrix,upload_clouds,expected_configs",
    [
        pytest.param(
            builder.ConfigMatrix(
                bases=(state.BaseImage.FOCAL, state.BaseImage.JAMMY, state.BaseImage.NOBLE),
            ),
            ("test-upload",),
            (
                builder.FetchConfig(
                    arch=TEST_STATIC_CONFIG.image_config.arch,
                    base=state.BaseImage.FOCAL,
                    cloud_id="test-upload",
                    prefix=TEST_STATIC_CONFIG.cloud_config.resource_prefix,
                ),
                builder.FetchConfig(
                    arch=TEST_STATIC_CONFIG.image_config.arch,
                    base=state.BaseImage.JAMMY,
                    cloud_id="test-upload",
                    prefix=TEST_STATIC_CONFIG.cloud_config.resource_prefix,
                ),
                builder.FetchConfig(
                    arch=TEST_STATIC_CONFIG.image_config.arch,
                    base=state.BaseImage.NOBLE,
                    cloud_id="test-upload",
                    prefix=TEST_STATIC_CONFIG.cloud_config.resource_prefix,
                ),
            ),
            id="multiple OS bases",
        ),
        pytest.param(
            builder.ConfigMatrix(
                bases=(state.BaseImage.FOCAL,),
            ),
            ("test-upload",),
            (
                builder.FetchConfig(
                    arch=TEST_STATIC_CONFIG.image_config.arch,
                    base=state.BaseImage.FOCAL,
                    cloud_id="test-upload",
                    prefix=TEST_STATIC_CONFIG.cloud_config.resource_prefix,
                ),
            ),
            id="single OS base",
        ),
        # multiple upload clouds
        pytest.param(
            builder.ConfigMatrix(
                bases=(state.BaseImage.FOCAL,),
            ),
            ("test-upload-a", "test-upload-b"),
            (
                builder.FetchConfig(
                    arch=TEST_STATIC_CONFIG.image_config.arch,
                    base=state.BaseImage.FOCAL,
                    cloud_id="test-upload-a",
                    prefix=TEST_STATIC_CONFIG.cloud_config.resource_prefix,
                ),
                builder.FetchConfig(
                    arch=TEST_STATIC_CONFIG.image_config.arch,
                    base=state.BaseImage.FOCAL,
                    cloud_id="test-upload-b",
                    prefix=TEST_STATIC_CONFIG.cloud_config.resource_prefix,
                ),
            ),
            id="multiple upload clouds",
        ),
        # multiple upload clouds with multiple OS bases
        pytest.param(
            builder.ConfigMatrix(
                bases=(state.BaseImage.FOCAL, state.BaseImage.JAMMY),
            ),
            ("test-upload-a", "test-upload-b"),
            (
                builder.FetchConfig(
                    arch=TEST_STATIC_CONFIG.image_config.arch,
                    base=state.BaseImage.FOCAL,
                    cloud_id="test-upload-a",
                    prefix=TEST_STATIC_CONFIG.cloud_config.resource_prefix,
                ),
                builder.FetchConfig(
                    arch=TEST_STATIC_CONFIG.image_config.arch,
                    base=state.BaseImage.FOCAL,
                    cloud_id="test-upload-b",
                    prefix=TEST_STATIC_CONFIG.cloud_config.resource_prefix,
                ),
                builder.FetchConfig(
                    arch=TEST_STATIC_CONFIG.image_config.arch,
                    base=state.BaseImage.JAMMY,
                    cloud_id="test-upload-a",
                    prefix=TEST_STATIC_CONFIG.cloud_config.resource_prefix,
                ),
                builder.FetchConfig(
                    arch=TEST_STATIC_CONFIG.image_config.arch,
                    base=state.BaseImage.JAMMY,
                    cloud_id="test-upload-b",
                    prefix=TEST_STATIC_CONFIG.cloud_config.resource_prefix,
                ),
            ),
            id="multiple upload clouds with multiple OS bases",
        ),
    ],
)
def test__parametrize_fetch(
    config_matrix: builder.ConfigMatrix,
    upload_clouds: typing.Iterable[str],
    expected_configs: tuple[builder.FetchConfig, ...],
):
    """
    arrange: given fetch configuration values.
    act: when _parametrize_fetch is called.
    assert: expected fetch configurations are returned.
    """
    static_config = factories.StaticConfigFactory.create()
    static_config.cloud_config.upload_clouds = upload_clouds
    assert (
        builder._parametrize_fetch(config_matrix=config_matrix, static_config=static_config)
        == expected_configs
    )


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
        builder.get_latest_images(config_matrix=MagicMock(), static_config=MagicMock())


def test_get_latest_images(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched _run function.
    act: when get_latest_images is called.
    assert: get_latest_images results are returned.
    """
    monkeypatch.setattr(builder, "_parametrize_fetch", MagicMock(return_value=["test1", "test2"]))
    monkeypatch.setattr(builder, "_get_latest_image", _patched__get_latest_image)

    assert [
        builder.CloudImage(
            arch=state.Arch.X64, base=state.BaseImage.NOBLE, cloud_id=cloud_id, image_id="test_id"
        )
        for cloud_id in ["test1", "test2"]
    ] == builder.get_latest_images(config_matrix=MagicMock(), static_config=MagicMock())


def test_get_latest_filters_empty_images(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched _run function that returns empty image id for the latest image.
    act: when get_latest_images is called.
    assert: get_latest_images returns only those images that have non-empty image id.
    """
    monkeypatch.setattr(
        builder, "_parametrize_fetch", MagicMock(return_value=["empty-image", "test2"])
    )

    monkeypatch.setattr(builder, "_get_latest_image", _patched__get_latest_image)

    assert [
        builder.CloudImage(
            arch=state.Arch.X64, base=state.BaseImage.NOBLE, cloud_id="test2", image_id="test_id"
        )
    ] == builder.get_latest_images(config_matrix=MagicMock(), static_config=MagicMock())


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
