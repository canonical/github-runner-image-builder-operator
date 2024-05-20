# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for builder module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

from pathlib import Path
from typing import NamedTuple
from unittest.mock import MagicMock

import pytest

import builder
from builder import (
    Arch,
    BaseImage,
    BuilderSetupError,
    DependencyInstallError,
    ImageBuilderInstallError,
    apt,
    subprocess,
)


def test_setup_builder_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched internal funcs that raises an error.
    act: when setup_builder is called.
    assert: BuilderSetupError is raised.
    """
    monkeypatch.setattr(builder, "_create_callback_script", MagicMock())
    monkeypatch.setattr(
        builder,
        "_install_image_builder",
        MagicMock(side_effect=ImageBuilderInstallError("Failed to install image builder.")),
    )

    with pytest.raises(BuilderSetupError) as exc:
        builder.setup_builder(callback_config=MagicMock(), cron_config=MagicMock())

    assert "Failed to install image builder." in str(exc.getrepr())


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
        "_create_callback_script",
        (create_callback_script_mock := MagicMock()),
    )
    monkeypatch.setattr(
        builder,
        "_install_image_builder",
        (image_mock := MagicMock()),
    )
    monkeypatch.setattr(
        builder,
        "install_cron",
        (install_cron_mock := MagicMock()),
    )

    builder.setup_builder(callback_config=MagicMock(), cron_config=MagicMock())

    deps_mock.assert_called_once()
    create_callback_script_mock.assert_called_once()
    image_mock.assert_called_once()
    install_cron_mock.assert_called_once()


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


def test__create_callback_script(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """
    arrange: given monkeypatched CALLBACK_SCRIPT_PATH.
    act: when _create_callback_script is called.
    assert: expected contents are written to path.
    """
    test_path = tmp_path / "test"
    monkeypatch.setattr(builder, "CALLBACK_SCRIPT_PATH", test_path)
    test_config = builder.CallbackConfig(
        model_name="test-model",
        unit_name="test-unit/0",
        charm_dir="test_dir",
        hook_name="test-hook",
    )

    builder._create_callback_script(config=test_config)

    contents = test_path.read_text(encoding="utf-8")
    assert (
        contents
        == f"""#! /bin/bash
OPENSTACK_IMAGE_ID="$1"

/usr/bin/juju-exec {test_config.unit_name} \
JUJU_DISPATCH_PATH="hooks/{test_config.hook_name}" \
JUJU_MODEL_NAME="{test_config.model_name}" \
JUJU_UNIT_NAME="{test_config.unit_name}" \
OPENSTACK_IMAGE_ID="$OPENSTACK_IMAGE_ID" \
{test_config.charm_dir}/dispatch
"""
    )


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

    with pytest.raises(ImageBuilderInstallError) as exc:
        builder._install_image_builder()

    assert "error running image builder install" in str(exc.getrepr())


def test_install_cron_no_reconfigure(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched _should_configure_cron which returns False, denoting no change.
    act: when install_cron is callec.
    assert: cron service is not restarted.
    """
    monkeypatch.setattr(builder, "_should_configure_cron", MagicMock(return_value=False))
    monkeypatch.setattr(builder, "service_restart", (service_restart_mock := MagicMock()))

    builder.install_cron(config=MagicMock())

    service_restart_mock.assert_not_called()


def test_install_cron(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """
    arrange: given monkeypatched subfunctions of install_cron.
    act: when install_cron is called.
    assert: subfunctions are called and cron file is written with expected contents.
    """
    monkeypatch.setattr(builder, "_should_configure_cron", MagicMock())
    monkeypatch.setattr(builder, "service_restart", (service_restart_mock := MagicMock()))
    test_path = tmp_path / "test"
    monkeypatch.setattr(builder, "CRON_BUILD_SCHEDULE_PATH", test_path)
    test_config = builder.RunCronConfig(
        arch=Arch.ARM64,
        base=BaseImage.JAMMY,
        charm_meta=builder.CharmMeta(
            app_name="test-app", model_name="test-model", unit_name="test-unit"
        ),
        cloud_name="test-cloud",
        interval=5,
        num_revisions=5,
    )

    builder.install_cron(config=test_config)

    service_restart_mock.assert_called_once()
    cron_contents = test_path.read_text(encoding="utf-8")
    assert (
        cron_contents
        == f"""0 */{test_config.interval} * * * ubuntu HOME=/home/ubuntu /usr/bin/sudo \
--preserve-env /home/ubuntu/.local/bin/github-runner-image-builder build \
--image-base {test_config.base.value} \
--cloud-name {test_config.cloud_name} \
--num-revisions {test_config.num_revisions} \
--callback-script-path propagate_image_id \
--output-image-name {test_config.base.value}-{test_config.charm_meta.app_name}-\
{test_config.arch.value}
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
            """0 */5 * * * ubuntu HOME=/home/ubuntu /usr/bin/sudo \
--preserve-env /home/ubuntu/.local/bin/github-runner-image-builder build \
--image-base jammy \
--cloud-name test-cloud \
--num-revisions 5 \
--callback-script-path propagate_image_id \
--output-image-name output-image-name
""",
            ShoudReconfigureCronInputs(2, BaseImage.JAMMY, "test-cloud", 5),
            True,
            id="interval changed",
        ),
        pytest.param(
            """0 */5 * * * ubuntu HOME=/home/ubuntu /usr/bin/sudo \
--preserve-env /home/ubuntu/.local/bin/github-runner-image-builder build \
--image-base noble \
--cloud-name test-cloud \
--num-revisions 5 \
--callback-script-path propagate_image_id \
--output-image-name output-image-name
""",
            ShoudReconfigureCronInputs(2, BaseImage.JAMMY, "test-cloud", 5),
            True,
            id="image_base changed",
        ),
        pytest.param(
            """0 */5 * * * ubuntu HOME=/home/ubuntu /usr/bin/sudo \
--preserve-env /home/ubuntu/.local/bin/github-runner-image-builder build \
--image-base jammy \
--cloud-name test-cloud-changed \
--num-revisions 5 \
--callback-script-path propagate_image_id \
--output-image-name output-image-name
""",
            ShoudReconfigureCronInputs(5, BaseImage.JAMMY, "test-cloud", 5),
            True,
            id="cloud_name changed",
        ),
        pytest.param(
            """0 */5 * * * ubuntu HOME=/home/ubuntu /usr/bin/sudo \
--preserve-env /home/ubuntu/.local/bin/github-runner-image-builder build \
--image-base jammy \
--cloud-name test-cloud \
--num-revisions 2 \
--callback-script-path propagate_image_id \
--output-image-name output-image-name
""",
            ShoudReconfigureCronInputs(5, BaseImage.JAMMY, "test-cloud", 5),
            True,
            id="num_revisions changed",
        ),
        pytest.param(
            """0 */5 * * * ubuntu HOME=/home/ubuntu /usr/bin/sudo \
--preserve-env /home/ubuntu/.local/bin/github-runner-image-builder build \
--image-base jammy \
--cloud-name test-cloud \
--num-revisions 5 \
--callback-script-path propagate_image_id \
--output-image-name output-image-name
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
