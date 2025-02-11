# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for builder module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

import time
from pathlib import Path
from typing import Any, Type
from unittest.mock import MagicMock

import pytest

from github_runner_image_builder import builder, cloud_image, config
from github_runner_image_builder.builder import (
    BuildImageError,
    ChrootBaseError,
    DependencyInstallError,
    HomeDirectoryChangeOwnershipError,
    ImageCompressError,
    ImageConnectError,
    ImageResizeError,
    NetworkBlockDeviceError,
    PermissionConfigurationError,
    ResizePartitionError,
    SystemUserConfigurationError,
    UnattendedUpgradeDisableError,
    YarnInstallError,
    YQBuildError,
    shutil,
    subprocess,
)
from tests.unit import factories


@pytest.mark.parametrize(
    "func, args",
    [
        pytest.param("_unmount_build_path", [], id="unmount build path"),
        pytest.param("_install_dependencies", [], id="install dependencies"),
        pytest.param("_enable_network_block_device", [], id="enable network block device"),
        pytest.param("_resize_image", [MagicMock()], id="resize image"),
        pytest.param("_resize_mount_partitions", [], id="resize mount partitions"),
        pytest.param("_disable_unattended_upgrades", [], id="disable unattended upgrades"),
        pytest.param("_configure_system_users", [], id="configure system users"),
        pytest.param("_configure_usr_local_bin", [], id="configure /usr/local/bin"),
        pytest.param("_compress_image", [MagicMock()], id="compress image"),
    ],
)
def test_subprocess_call_funcs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, func: str, args: list[Any]
):
    """
    arrange: given functions that consist of subprocess calls only with mocked subprocess calls.
    act: when the function is called.
    assert: no errors are raised.
    """
    monkeypatch.setattr(subprocess, "check_output", MagicMock())
    monkeypatch.setattr(subprocess, "run", MagicMock())
    monkeypatch.setattr(builder, "UBUNTU_HOME", tmp_path)
    # Bypass decorated retry sleep
    monkeypatch.setattr(time, "sleep", MagicMock())

    assert getattr(builder, func)(*args) is None


@pytest.mark.parametrize(
    "func, args, exc",
    [
        pytest.param(
            "_unmount_build_path", [], builder.UnmountBuildPathError, id="unmount build path"
        ),
        pytest.param("_resize_image", [MagicMock()], builder.ImageResizeError, id="resize image"),
        pytest.param(
            "_connect_image_to_network_block_device",
            [MagicMock()],
            builder.ImageConnectError,
            id="connect image to nbd",
        ),
        pytest.param(
            "_resize_mount_partitions", [], builder.ResizePartitionError, id="resize mount parts"
        ),
        pytest.param("_install_yq", [], builder.YQBuildError, id="install yq"),
        pytest.param(
            "_disable_unattended_upgrades",
            [],
            builder.UnattendedUpgradeDisableError,
            id="disable unattende upgrades",
        ),
        pytest.param(
            "_configure_system_users",
            [],
            builder.SystemUserConfigurationError,
            id="configure system users",
        ),
        pytest.param(
            "_configure_usr_local_bin",
            [],
            builder.PermissionConfigurationError,
            id="configure system users",
        ),
        pytest.param(
            "_install_yarn",
            [],
            builder.YarnInstallError,
            id="install yarn",
        ),
        pytest.param(
            "_disconnect_image_to_network_block_device",
            [],
            builder.ImageConnectError,
            id="disconnect image to nbd",
        ),
    ],
)
def test_subprocess_func_errors(
    monkeypatch: pytest.MonkeyPatch, func: str, args: list[Any], exc: Type[Exception]
):
    """
    arrange: given functions with subprocess calls that is monkeypatched to raise exceptions.
    act: when the function is called.
    assert: subprocess error is wrapped to expected error.
    """
    monkeypatch.setattr(
        subprocess,
        "check_output",
        MagicMock(side_effect=subprocess.SubprocessError("Test subprocess error")),
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        MagicMock(side_effect=subprocess.SubprocessError("Test subprocess error")),
    )
    # Bypass decorated retry sleep
    monkeypatch.setattr(time, "sleep", MagicMock())

    with pytest.raises(exc):
        getattr(builder, func)(*args)


def test_initialize(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given sub functions of initialize.
    act: when initialize is called.
    assert: the subfunctions are called.
    """
    monkeypatch.setattr(builder, "_install_dependencies", (install_mock := MagicMock()))
    monkeypatch.setattr(builder, "_enable_network_block_device", (enable_nbd_mock := MagicMock()))

    builder.initialize()

    install_mock.assert_called_with()
    enable_nbd_mock.assert_called_with()


def test__install_dependencies_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given mocked subprocess.check_output calls that raises CalledProcessError.
    act: when _install_dependencies is called.
    assert: DependencyInstallError is raised.
    """
    monkeypatch.setattr(
        subprocess,
        "check_output",
        MagicMock(
            side_effect=[None, None, subprocess.CalledProcessError(1, [], "Package not found.")]
        ),
    )

    with pytest.raises(DependencyInstallError) as exc:
        builder._install_dependencies()

    assert "Package not found" in str(exc.getrepr())


def test__enable_network_block_device_fail(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given subprocess run that raises CalledProcessError.
    act: when _enable_network_block_device is called.
    assert: NetworkBlockDeviceError is raised.
    """
    monkeypatch.setattr(
        subprocess,
        "check_output",
        MagicMock(side_effect=subprocess.CalledProcessError(1, [], "Module nbd not found")),
    )

    with pytest.raises(NetworkBlockDeviceError) as exc:
        builder._enable_network_block_device()

    assert "Module nbd not found" in str(exc.getrepr())


@pytest.mark.parametrize(
    "patch_obj, sub_func, mock, expected_message",
    [
        pytest.param(
            builder,
            "_resize_mount_partitions",
            MagicMock(side_effect=ResizePartitionError("Partition resize failed")),
            "Partition resize failed",
            id="Partition resize failed",
        ),
        pytest.param(
            builder,
            "ChrootContextManager",
            MagicMock(side_effect=ChrootBaseError("Failed to chroot into dir")),
            "Failed to chroot into dir",
            id="Failed to chroot into dir",
        ),
        pytest.param(
            builder,
            "_compress_image",
            MagicMock(side_effect=ImageCompressError("Failed to compress image")),
            "Failed to compress image",
            id="Failed to compress image",
        ),
        pytest.param(
            builder.store,
            "upload_image",
            MagicMock(side_effect=ImageCompressError("Failed to upload image")),
            "Failed to upload image",
            id="Failed to upload image",
        ),
    ],
)
def test_run_error(
    patch_obj: Any,
    sub_func: str,
    mock: MagicMock,
    expected_message: str,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: given a monkeypatched functions of run that raises exceptions.
    act: when run is called.
    assert: BuildImageError is raised.
    """
    monkeypatch.setattr(builder, "IMAGE_MOUNT_DIR", MagicMock())
    monkeypatch.setattr(cloud_image, "download_and_validate_image", MagicMock())
    monkeypatch.setattr(builder, "_resize_image", MagicMock())
    monkeypatch.setattr(builder, "_connect_image_to_network_block_device", MagicMock())
    monkeypatch.setattr(builder, "_resize_mount_partitions", MagicMock())
    monkeypatch.setattr(builder, "_replace_mounted_resolv_conf", MagicMock())
    monkeypatch.setattr(builder, "_install_yq", MagicMock())
    monkeypatch.setattr(builder, "ChrootContextManager", MagicMock())
    monkeypatch.setattr(builder.subprocess, "check_output", MagicMock())
    monkeypatch.setattr(builder.subprocess, "run", MagicMock())
    monkeypatch.setattr(builder, "_disable_unattended_upgrades", MagicMock())
    monkeypatch.setattr(builder, "_enable_network_fair_queuing_congestion", MagicMock())
    monkeypatch.setattr(builder, "_configure_system_users", MagicMock())
    monkeypatch.setattr(builder, "_install_yarn", MagicMock())
    monkeypatch.setattr(builder, "_install_github_runner", MagicMock())
    monkeypatch.setattr(builder, "_chown_home", MagicMock())
    monkeypatch.setattr(builder, "_disconnect_image_to_network_block_device", MagicMock())
    monkeypatch.setattr(builder, "_compress_image", MagicMock())
    monkeypatch.setattr(patch_obj, sub_func, mock)

    with pytest.raises(BuildImageError) as exc:
        builder.run(cloud_name=MagicMock(), image_config=MagicMock(), keep_revisions=MagicMock())

    assert expected_message in str(exc.getrepr())


def test_run(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched functions of run that raises exceptions.
    act: when run is called.
    assert: BuildImageError is raised.
    """
    monkeypatch.setattr(builder, "IMAGE_MOUNT_DIR", MagicMock())
    monkeypatch.setattr(cloud_image, "download_and_validate_image", MagicMock())
    monkeypatch.setattr(builder, "_resize_image", MagicMock())
    monkeypatch.setattr(builder, "_connect_image_to_network_block_device", MagicMock())
    monkeypatch.setattr(builder, "_resize_mount_partitions", MagicMock())
    monkeypatch.setattr(builder, "_replace_mounted_resolv_conf", MagicMock())
    monkeypatch.setattr(builder, "_install_yq", MagicMock())
    monkeypatch.setattr(builder, "ChrootContextManager", MagicMock())
    monkeypatch.setattr(builder.subprocess, "check_output", MagicMock())
    monkeypatch.setattr(builder.subprocess, "run", MagicMock())
    monkeypatch.setattr(builder, "_disable_unattended_upgrades", MagicMock())
    monkeypatch.setattr(builder, "_enable_network_fair_queuing_congestion", MagicMock())
    monkeypatch.setattr(builder, "_configure_system_users", MagicMock())
    monkeypatch.setattr(builder, "_install_yarn", MagicMock())
    monkeypatch.setattr(builder, "_install_github_runner", MagicMock())
    monkeypatch.setattr(builder, "_chown_home", MagicMock())
    monkeypatch.setattr(builder, "_disconnect_image_to_network_block_device", MagicMock())
    monkeypatch.setattr(builder, "_compress_image", MagicMock())
    monkeypatch.setattr(
        builder.store, "upload_image", MagicMock(return_value=(test_image := MagicMock()))
    )

    assert (
        builder.run(cloud_name=MagicMock(), image_config=MagicMock(), keep_revisions=MagicMock())
        == test_image.id
    )


def test__resize_image_fail(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched subprocess.run that raises an exception.
    act: when _resize_image is called.
    assert: ImageResizeError is raised.
    """
    mock_run = MagicMock(
        side_effect=subprocess.CalledProcessError(
            returncode=1, cmd=[], output="", stderr="resize error"
        )
    )
    monkeypatch.setattr(
        subprocess,
        "check_output",
        mock_run,
    )

    with pytest.raises(ImageResizeError) as exc:
        builder._resize_image(image_path=MagicMock())

    assert "resize error" in str(exc.getrepr())


def test__mount_network_block_device_partition(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched mock subprocess run.
    act: when _mount_network_block_device_partition is called.
    assert: subprocess run call is made.
    """
    monkeypatch.setattr(subprocess, "check_output", (mock_run_call := MagicMock()))

    builder._mount_network_block_device_partition()

    mock_run_call.assert_called_once()


def test__connect_image_to_network_block_device_fail(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched process calls that fails.
    act: when _connect_image_to_network_block_device is called.
    assert: ImageMountError is raised.
    """
    monkeypatch.setattr(
        subprocess,
        "check_output",
        MagicMock(side_effect=subprocess.CalledProcessError(1, [], "", "error mounting")),
    )

    with pytest.raises(ImageConnectError) as exc:
        builder._connect_image_to_network_block_device(image_path=MagicMock())

    assert "error mounting" in str(exc.getrepr())


def test__connect_image_to_network_block_device(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched mock process run calls and \
        _mount_network_block_device_partition call.
    act: when _connect_image_to_network_block_device is called.
    assert: expected calls are made.
    """
    monkeypatch.setattr(subprocess, "check_output", (run_mock := MagicMock()))

    builder._connect_image_to_network_block_device(image_path=MagicMock())

    run_mock.assert_called_with(
        ["/usr/bin/mount", "-o", "rw", "/dev/nbd0p1", "/mnt/ubuntu-image"], timeout=60
    )


def test__replace_mounted_resolv_conf(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched MOUNTED_RESOLV_CONF_PATH and shutil.copy call.
    act: when _replace_mounted_resolv_conf.
    assert: expected calls are made on the mocks.
    """
    mock_mounted_resolv_conf_path = MagicMock()
    mock_copy = MagicMock()
    monkeypatch.setattr(builder, "MOUNTED_RESOLV_CONF_PATH", mock_mounted_resolv_conf_path)
    monkeypatch.setattr(builder.shutil, "copy", mock_copy)

    builder._replace_mounted_resolv_conf()

    mock_mounted_resolv_conf_path.unlink.assert_called_once()
    mock_copy.assert_called_once()


def test__resize_mount_partitions(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched subprocess calls that raises CalledProcessError.
    act: when _resize_mount_partitions is called
    assert: ResizePartitionError is raised.
    """
    monkeypatch.setattr(
        subprocess,
        "check_output",
        MagicMock(side_effect=[None, subprocess.CalledProcessError(1, [], "", "resize error")]),
    )

    with pytest.raises(ResizePartitionError) as exc:
        builder._resize_mount_partitions()

    assert "resize error" in str(exc.getrepr())


def test__install_yq_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched subprocess.run function that raises an error.
    act: when _install_yq is called.
    assert: YQBuildError is raised.
    """
    # Bypass decorated retry sleep
    monkeypatch.setattr(time, "sleep", MagicMock())
    monkeypatch.setattr(
        subprocess,
        "check_output",
        MagicMock(
            # tried 3 times via retry
            side_effect=[None, subprocess.CalledProcessError(1, [], "", "Go build error.")]
            * 3
        ),
    )

    with pytest.raises(YQBuildError) as exc:
        builder._install_yq()

    assert "Go build error" in str(exc.getrepr())


def test__install_yq_already_exists(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched yq mocked path that already exists.
    act: when _install_yq is called.
    assert: Mock functions are called.
    """
    # Bypass decorated retry sleep
    monkeypatch.setattr(time, "sleep", MagicMock())
    monkeypatch.setattr(builder, "YQ_REPOSITORY_PATH", MagicMock(return_value=True))
    monkeypatch.setattr(subprocess, "check_output", (run_mock := MagicMock()))
    monkeypatch.setattr(shutil, "copy", (copy_mock := MagicMock()))

    builder._install_yq()

    run_mock.assert_called()
    copy_mock.assert_called()


def test__install_yq(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched yq install mock functions.
    act: when _install_yq is called.
    assert: Mock functions are called.
    """
    # Bypass decorated retry sleep
    monkeypatch.setattr(time, "sleep", MagicMock())
    monkeypatch.setattr(subprocess, "check_output", (check_output_mock := MagicMock()))
    monkeypatch.setattr(shutil, "copy", (copy_mock := MagicMock()))

    builder._install_yq()

    check_output_mock.assert_called_with(
        ["/snap/bin/go", "build", "-C", "yq_source", "-o", "/usr/bin/yq"], timeout=1200
    )
    copy_mock.assert_called_with(Path("/usr/bin/yq"), Path("/mnt/ubuntu-image/usr/bin/yq"))


def test__disable_unattended_upgrades_subprocess_fail(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched subprocess run function that raises SubprocessError.
    act: when _disable_unattended_upgrades is called.
    assert: the UnattendedUpgradeDisableError is raised.
    """
    # Pylint thinks the testing mock patches are duplicate code (side effects are different).
    # pylint: disable=duplicate-code
    monkeypatch.setattr(
        subprocess,
        "check_output",
        MagicMock(
            side_effect=[
                *([None] * 4),
                subprocess.CalledProcessError(1, [], "Failed to disable unattended upgrades", ""),
            ]
        ),
    )

    with pytest.raises(UnattendedUpgradeDisableError) as exc:
        builder._disable_unattended_upgrades()

    assert "Failed to disable unattended upgrades" in str(exc.getrepr())


def test__enable_network_fair_queuing_congestion(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """
    arrange: given monkeypatched sysctl.conf path and sysctl subprocess run.
    act: when _enable_network_fair_queuing_congestion is called.
    assert: the configuration are written correctly and config reload is called.
    """
    monkeypatch.setattr(builder, "SYSCTL_CONF_PATH", test_path := tmp_path / "sysctl.conf")

    builder._enable_network_fair_queuing_congestion()

    config_contents = test_path.read_text(encoding="utf-8")
    assert "net.core.default_qdisc=fq" in config_contents
    assert "net.ipv4.tcp_congestion_control=bbr" in config_contents


def test__configure_system_users(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched subprocess run calls that raises an exception.
    act: when _configure_system_users is called.
    assert: SystemUserConfigurationError is raised.
    """
    monkeypatch.setattr(builder, "UBUNTU_HOME", MagicMock())
    monkeypatch.setattr(
        builder.subprocess,
        "check_output",
        MagicMock(
            side_effect=[
                *([None] * 2),
                subprocess.CalledProcessError(1, [], "Failed to add group.", ""),
            ]
        ),
    )

    with pytest.raises(SystemUserConfigurationError) as exc:
        builder._configure_system_users()

    assert "Failed to add group." in str(exc.getrepr())


def test__configure_usr_local_bin(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched subprocess run calls that raises an exception.
    act: when _configure_usr_local_bin is called.
    assert: PermissionConfigurationError is raised.
    """
    monkeypatch.setattr(
        builder.subprocess,
        "check_output",
        MagicMock(
            side_effect=subprocess.CalledProcessError(1, [], "Failed change permissions.", ""),
        ),
    )

    with pytest.raises(PermissionConfigurationError) as exc:
        builder._configure_usr_local_bin()

    assert "Failed change permissions." in str(exc.getrepr())


def test__install_yarn_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched subprocess.run that raises an error.
    act: when _install_yarn is called.
    assert: ExternalPackageInstallError is raised.
    """
    # The test mocks use similar codes.
    monkeypatch.setattr(  # pylint: disable=duplicate-code
        subprocess,
        "check_output",
        MagicMock(
            side_effect=[
                None,
                subprocess.CalledProcessError(1, [], "Failed to clean npm cache.", ""),
            ]
        ),
    )

    with pytest.raises(YarnInstallError) as exc:
        builder._install_yarn()

    assert "Failed to clean npm cache." in str(exc.getrepr())


def test__install_yarn(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched functions of _install_yarn.
    act: when _install_yarn is called.
    assert: The function exists without raising an error.
    """
    monkeypatch.setattr(subprocess, "check_output", MagicMock())

    assert builder._install_yarn() is None


@pytest.mark.parametrize(
    "module, func, mock, expected_message",
    [
        pytest.param(
            builder.requests,
            "get",
            MagicMock(side_effect=builder.requests.exceptions.RequestException),
            "Unable to fetch the latest release version.",
        ),
        pytest.param(
            builder.requests,
            "get",
            MagicMock(return_value=factories.MockRequestsReponseFactory(is_redirect=False)),
            "Failed to download runner, invalid redirect.",
        ),
        pytest.param(
            builder.urllib.request,
            "urlopen",
            MagicMock(side_effect=builder.urllib.error.URLError(reason="not found")),
            "Error downloading runner tar archive.",
        ),
        pytest.param(
            builder.tarfile,
            "open",
            MagicMock(side_effect=builder.tarfile.TarError),
            "Error extracting runner tar archive.",
        ),
        pytest.param(
            builder.subprocess,
            "check_call",
            MagicMock(side_effect=subprocess.SubprocessError()),
            "Error changing github runner directory.",
        ),
    ],
)
def test__install_github_runner_error(
    monkeypatch: pytest.MonkeyPatch, module: Any, func: str, mock: MagicMock, expected_message: str
):
    """
    arrange: given monkeypatched dependency functions that raise an error.
    act: when _install_github_runner is called.
    assert: RunnerDownloadError is raised.
    """
    monkeypatch.setattr(builder.requests, "get", MagicMock())
    monkeypatch.setattr(builder.urllib.request, "urlopen", MagicMock())
    monkeypatch.setattr(builder.tarfile, "open", MagicMock())
    monkeypatch.setattr(builder, "ACTIONS_RUNNER_PATH", MagicMock())
    monkeypatch.setattr(builder, "BytesIO", MagicMock())
    monkeypatch.setattr(builder.pwd, "getpwnam", MagicMock())
    monkeypatch.setattr(builder.subprocess, "check_call", MagicMock())
    monkeypatch.setattr(module, func, mock)

    with pytest.raises(builder.RunnerDownloadError) as exc:
        builder._install_github_runner(arch=config.Arch.X64, version="")

    assert expected_message in str(exc.getrepr())


def test__install_github_runner(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched dependency functions.
    act: when _install_github_runner is called.
    assert: no errors are raised.
    """
    monkeypatch.setattr(builder.requests, "get", MagicMock())
    monkeypatch.setattr(builder.urllib.request, "urlopen", MagicMock())
    monkeypatch.setattr(builder.tarfile, "open", MagicMock())
    monkeypatch.setattr(builder, "ACTIONS_RUNNER_PATH", MagicMock())
    monkeypatch.setattr(builder, "BytesIO", MagicMock())
    monkeypatch.setattr(builder.pwd, "getpwnam", MagicMock())
    monkeypatch.setattr(builder.subprocess, "check_call", MagicMock())

    builder._install_github_runner(arch=config.Arch.ARM64, version="")


@pytest.mark.parametrize(
    "version, expected_version",
    [
        pytest.param("v2.220.0", "2.220.0", id="with v prefix"),
        pytest.param("2.220.0", "2.220.0", id="without v prefix"),
    ],
)
def test__get_github_runner_version_user_defined(version: str, expected_version: str):
    """
    arrange: given user defined GitHub runner version.
    act: when _get_github_runner_version is called.
    assert: the user provided version is returned.
    """
    assert builder._get_github_runner_version(version=version) == expected_version


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(
            subprocess.CalledProcessError(1, [], "Something happened", ""),
            id="called process error",
        ),
        pytest.param(
            subprocess.SubprocessError(),
            id="general subprocess error",
        ),
    ],
)
def test__chown_home_fail(
    monkeypatch: pytest.MonkeyPatch,
    error: subprocess.CalledProcessError | subprocess.SubprocessError,
):
    """
    arrange: given a monkeypatched process calls that fails.
    act: when _disconnect_image_to_network_block_device is called.
    assert: ImageMountError is raised.
    """
    monkeypatch.setattr(
        subprocess,
        "check_call",
        MagicMock(side_effect=error),
    )

    with pytest.raises(HomeDirectoryChangeOwnershipError):
        builder._chown_home()


def test__disconnect_image_to_network_block_device_fail(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched process calls that fails.
    act: when _disconnect_image_to_network_block_device is called.
    assert: ImageMountError is raised.
    """
    monkeypatch.setattr(
        subprocess,
        "run",
        MagicMock(side_effect=subprocess.CalledProcessError(1, [], "", "error mounting")),
    )

    with pytest.raises(ImageConnectError) as exc:
        builder._disconnect_image_to_network_block_device()

    assert "error mounting" in str(exc.getrepr())


def test__disconnect_image_to_network_block_device(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched mock process run calls and \
        _mount_network_block_device_partition call.
    act: when _disconnect_image_to_network_block_device is called.
    assert: expected calls are made.
    """
    monkeypatch.setattr(subprocess, "run", (check_mock := MagicMock()))

    builder._disconnect_image_to_network_block_device()

    check_mock.assert_called_with(
        ["/usr/bin/qemu-nbd", "--disconnect", "/dev/nbd0p1"],
        check=True,
        encoding="utf-8",
        timeout=30,
    )


def test__compress_image_fail(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given subprocess run that raises CalledProcessError.
    act: when _compress_image is called.
    assert: ImageCompressError is raised.
    """
    # Bypass decorated retry sleep
    monkeypatch.setattr(time, "sleep", MagicMock())
    monkeypatch.setattr(
        subprocess, "run", MagicMock(return_value=subprocess.CompletedProcess([], 0, "", ""))
    )
    monkeypatch.setattr(
        subprocess,
        "check_output",
        MagicMock(side_effect=subprocess.CalledProcessError(1, [], "Compression error")),
    )

    with pytest.raises(ImageCompressError) as exc:
        builder._compress_image(image=MagicMock())

    assert "Compression error" in str(exc.getrepr())


def test__compress_image_subprocess_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given subprocess check_output raises an error.
    act: when _compress_image is called.
    assert: ImageCompressError is raised.
    """
    # Bypass decorated retry sleep
    monkeypatch.setattr(time, "sleep", MagicMock())
    monkeypatch.setattr(subprocess, "run", MagicMock())
    monkeypatch.setattr(
        subprocess,
        "check_output",
        MagicMock(side_effect=subprocess.SubprocessError("Image subprocess err")),
    )
    image_mock = MagicMock()

    with pytest.raises(builder.ImageCompressError) as exc:
        builder._compress_image(image=image_mock)

    assert "Image subprocess err" in str(exc.getrepr())
