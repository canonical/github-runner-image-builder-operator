# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for builder module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

from pathlib import Path
from typing import NamedTuple
from unittest.mock import MagicMock

import pytest
import yaml

import builder
from builder import (
    Arch,
    BaseImage,
    BuilderSetupError,
    DependencyInstallError,
    ImageBuilderInitializeError,
    apt,
    subprocess,
)


def test_setup_builder_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched internal funcs that raises an error.
    act: when setup_builder is called.
    assert: BuilderSetupError is raised.
    """
    monkeypatch.setattr(
        builder,
        "_install_dependencies",
        MagicMock(side_effect=DependencyInstallError("Failed to install dependencies.")),
    )

    with pytest.raises(BuilderSetupError) as exc:
        builder.setup_builder(build_config=MagicMock(), cloud_config=MagicMock(), interval=1)

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

    builder.setup_builder(build_config=MagicMock(), cloud_config=MagicMock(), interval=1)

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

    with pytest.raises(DependencyInstallError) as exc:
        builder._install_dependencies()

    assert "error installing deps" in str(exc.getrepr())


def test__install_dependencies(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: monkeypatched apt.add_package function.
    act: when _install_dependencies is called.
    assert: mocked functions are called.
    """
    monkeypatch.setattr(apt, "add_package", (apt_mock := MagicMock()))
    monkeypatch.setattr(subprocess, "run", (run_mock := MagicMock()))

    builder._install_dependencies()

    apt_mock.assert_called_once()
    run_mock.assert_called_once()


def test__install_image_builder_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched subprocess.run function that raises an error.
    act: when _install_image_builder is called.
    assert: ImageBuilderInstallError is raised.
    """
    monkeypatch.setattr(
        subprocess,
        "run",
        MagicMock(
            side_effect=subprocess.CalledProcessError(
                1, [], "", "error running image builder install"
            )
        ),
    )

    with pytest.raises(ImageBuilderInitializeError) as exc:
        builder._initialize_image_builder()

    assert "error running image builder install" in str(exc.getrepr())


def test_install_clouds_yaml_not_exists(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """
    arrange: given mocked empty OPENSTACK_CLOUDS_YAML_PATH.
    act: when install_clouds_yaml is called.
    assert: contents of cloud_config are written.
    """
    test_path = tmp_path / "not-exists"
    monkeypatch.setattr(builder, "OPENSTACK_CLOUDS_YAML_PATH", test_path)

    builder.install_clouds_yaml({"a": "b"})

    contents = test_path.read_text(encoding="utf-8")
    assert contents == "a: b\n"


@pytest.mark.parametrize(
    "original_contents, cloud_config",
    [
        pytest.param("", {"a": "b"}, id="changed"),
        pytest.param("a: b\n", {"a": "b"}, id="not changed"),
    ],
)
def test_install_clouds_yaml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, original_contents: str, cloud_config: dict
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
    assert contents == cloud_config


def test_configure_cron_no_reconfigure(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched _should_configure_cron which returns False, denoting no change.
    act: when configure_cron is called.
    assert: cron service is not restarted.
    """
    monkeypatch.setattr(builder, "_should_configure_cron", MagicMock(return_value=False))
    monkeypatch.setattr(builder.systemd, "service_restart", (service_restart_mock := MagicMock()))

    builder.configure_cron(build_config=MagicMock(), interval=1)

    service_restart_mock.assert_not_called()


def test_configure_cron(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
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
    test_config = builder.BuildConfig(
        arch=Arch.ARM64,
        base=BaseImage.JAMMY,
        app_name="test-app",
        cloud_name="test-cloud",
        callback_script=test_path,
        num_revisions=5,
    )

    builder.configure_cron(build_config=test_config, interval=test_interval)

    service_restart_mock.assert_called_once()
    cron_contents = test_path.read_text(encoding="utf-8")
    assert (
        cron_contents
        == f"""0 */{test_interval} * * * ubuntu HOME=/home/ubuntu /usr/bin/run-one \
/usr/bin/sudo \
--preserve-env /home/ubuntu/.local/bin/github-runner-image-builder run \
{test_config.cloud_name} \
{test_config.base.value}-{test_config.app_name}-{test_config.arch.value} \
--base-image {test_config.base.value} \
--keep-revisions {test_config.num_revisions} \
--callback-script {test_path} \
>> /home/ubuntu/github-runner-image-builder.log 2>&1
"""
    )


def test__should_configure_cron_no_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """
    arrange: given a monkeypatched CRON_BUILD_SCHEDULE_PATH that does not exist.
    act: when _should_configure_cron is called.
    assert: Truthy value is returned.
    """
    test_path = tmp_path / "not-exists"
    monkeypatch.setattr(builder, "CRON_BUILD_SCHEDULE_PATH", test_path)

    assert builder._should_configure_cron(
        interval=MagicMock(),
        image_base=MagicMock(),
        cloud_name=MagicMock(),
        num_revisions=MagicMock(),
    )


class ShoudReconfigureCronInputs(NamedTuple):
    """Wrapper to _should_configure_cron inputs for testing.

    Attributes:
        interval: Wrapped input value.
        image_base: Wrapped input value.
        cloud_name: Wrapped input value.
        num_revisions: Wrapped input value.
    """

    interval: int
    image_base: BaseImage
    cloud_name: str
    num_revisions: int


@pytest.mark.parametrize(
    "cron_contents, inputs, expected",
    [
        pytest.param(
            """0 */5 * * * ubuntu HOME=/home/ubuntu /usr/bin/run-one /usr/bin/sudo \
--preserve-env /home/ubuntu/.local/bin/github-runner-image-builder run \
test-cloud \
output-image-name \
--base-image jammy \
--keep-revisions 5 \
--callback-script propagate_image_id \
""",
            ShoudReconfigureCronInputs(2, BaseImage.JAMMY, "test-cloud", 5),
            True,
            id="interval changed",
        ),
        pytest.param(
            """0 */5 * * * ubuntu HOME=/home/ubuntu /usr/bin/run-one /usr/bin/sudo \
--preserve-env /home/ubuntu/.local/bin/github-runner-image-builder run \
test-cloud \
output-image-name \
--base-image jammy \
--keep-revisions 5 \
--callback-script propagate_image_id \
""",
            ShoudReconfigureCronInputs(2, BaseImage.NOBLE, "test-cloud", 5),
            True,
            id="image_base changed",
        ),
        pytest.param(
            """0 */5 * * * ubuntu HOME=/home/ubuntu /usr/bin/run-one /usr/bin/sudo \
--preserve-env /home/ubuntu/.local/bin/github-runner-image-builder run \
test-cloud \
output-image-name \
--base-image jammy \
--keep-revisions 5 \
--callback-script propagate_image_id \
""",
            ShoudReconfigureCronInputs(5, BaseImage.JAMMY, "test-cloud-change", 5),
            True,
            id="cloud_name changed",
        ),
        pytest.param(
            """0 */5 * * * ubuntu HOME=/home/ubuntu /usr/bin/run-one /usr/bin/sudo \
--preserve-env /home/ubuntu/.local/bin/github-runner-image-builder run \
test-cloud \
output-image-name \
--base-image jammy \
--keep-revisions 5 \
--callback-script propagate_image_id \
""",
            ShoudReconfigureCronInputs(5, BaseImage.JAMMY, "test-cloud", 7),
            True,
            id="num_revisions changed",
        ),
        pytest.param(
            """0 */5 * * * ubuntu HOME=/home/ubuntu /usr/bin/run-one /usr/bin/sudo \
--preserve-env /home/ubuntu/.local/bin/github-runner-image-builder run \
test-cloud \
output-image-name \
--base-image jammy \
--keep-revisions 5 \
--callback-script propagate_image_id \
""",
            ShoudReconfigureCronInputs(5, BaseImage.JAMMY, "test-cloud", 5),
            False,
            id="no change",
        ),
    ],
)
def test__should_configure_cron(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    cron_contents: str,
    inputs: ShoudReconfigureCronInputs,
    expected: bool,
):
    """
    arrange: given _should_configure_cron input values and monkeypatched CRON_BUILD_SCHEDULE_PATH.
    act: when _should_configure_cron is called.
    assert: expected value is returned.
    """
    test_path = tmp_path / "test"
    test_path.write_text(cron_contents, encoding="utf-8")
    monkeypatch.setattr(builder, "CRON_BUILD_SCHEDULE_PATH", test_path)

    assert (
        builder._should_configure_cron(
            interval=inputs.interval,
            image_base=inputs.image_base,
            cloud_name=inputs.cloud_name,
            num_revisions=inputs.num_revisions,
        )
        == expected
    )


def test_build_immediate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """
    arrange: given a monkeypatched subprocess call.
    act: when build_immediate is called.
    assert: the call to image builder is made.
    """
    monkeypatch.setattr(builder.subprocess, "Popen", popen_mock := MagicMock())

    testconfig = builder.BuildConfig(
        arch=Arch.ARM64,
        app_name="test",
        base=BaseImage.JAMMY,
        cloud_name="test",
        num_revisions=1,
        callback_script=tmp_path,
    )

    builder.build_immediate(config=testconfig)

    popen_mock.assert_called_once()


def test_get_latest_image_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched subprocess.run that raises an error.
    act: when get_latest_image is called.
    assert: GetLatestImageError is raised.
    """
    monkeypatch.setattr(
        builder.subprocess,
        "run",
        MagicMock(side_effect=subprocess.CalledProcessError(1, "", "", "openstack error")),
    )

    with pytest.raises(builder.GetLatestImageError) as exc:
        builder.get_latest_image(
            base=MagicMock(), app_name=MagicMock(), arch=MagicMock(), cloud_name=MagicMock()
        )

    assert "openstack error" in str(exc.getrepr())


def test_get_latest_image(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched subprocess.run that returns an image id.
    act: when get_latest_image is called.
    assert: image id is returned.
    """
    monkeypatch.setattr(
        builder.subprocess,
        "run",
        MagicMock(
            return_value=subprocess.CompletedProcess(
                args=MagicMock(), returncode=0, stdout="test-image", stderr=""
            )
        ),
    )

    assert "test-image" == builder.get_latest_image(
        base=MagicMock(), app_name=MagicMock(), arch=MagicMock(), cloud_name=MagicMock()
    )
