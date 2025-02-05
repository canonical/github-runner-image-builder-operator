# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for chroot module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

from unittest.mock import MagicMock

import pytest

from github_runner_image_builder.chroot import (
    ChrootContextManager,
    MountError,
    SyncError,
    os,
    subprocess,
)


def test_chroot_bind_fail(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched subprocess run call that fails.
    act: when chroot context is entered.
    assert: MountError is raised.
    """
    monkeypatch.setattr(
        subprocess,
        "run",
        MagicMock(
            side_effect=subprocess.CalledProcessError(
                returncode=1, cmd=[], output="", stderr="Failed to bind dirs"
            )
        ),
    )
    with pytest.raises(MountError) as exc:
        with ChrootContextManager(chroot_path=MagicMock()):
            pass

    assert "Failed to bind dirs" in str(exc.getrepr())


def test_chroot_unmount_fail(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched subprocess run call that fails.
    act: when chroot context is exited.
    assert: MountError is raised.
    """
    monkeypatch.setattr(os, "chroot", MagicMock())
    monkeypatch.setattr(os, "chdir", MagicMock())
    monkeypatch.setattr(
        subprocess,
        "run",
        MagicMock(
            side_effect=[
                *([None] * 5),
                subprocess.CalledProcessError(
                    returncode=1, cmd=[], output="", stderr="Failed to unmount dirs"
                ),
            ]
        ),
    )
    with pytest.raises(MountError) as exc:
        with ChrootContextManager(chroot_path=MagicMock()):
            pass

    assert "Failed to unmount dirs" in str(exc.getrepr())


def test_chroot_sync_fail(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched subprocess run call that fails.
    act: when chroot context is exited.
    assert: SyncError is raised.
    """
    monkeypatch.setattr(os, "chroot", MagicMock())
    monkeypatch.setattr(os, "chdir", MagicMock())
    monkeypatch.setattr(
        subprocess,
        "run",
        MagicMock(
            side_effect=[
                *([None] * 3),
                subprocess.CalledProcessError(
                    returncode=1, cmd=[], output="", stderr="Failed to sync dirs"
                ),
            ]
        ),
    )
    with pytest.raises(SyncError) as exc:
        with ChrootContextManager(chroot_path=MagicMock()):
            pass

    assert "Failed to sync dirs" in str(exc.getrepr())


def test_chroot_umount_fail(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched subprocess run call that fails.
    act: when chroot context is exited.
    assert: SyncError is raised.
    """
    monkeypatch.setattr(os, "chroot", MagicMock())
    monkeypatch.setattr(os, "chdir", MagicMock())
    monkeypatch.setattr(os, "fchdir", MagicMock())
    monkeypatch.setattr(os, "close", MagicMock())
    monkeypatch.setattr(
        subprocess,
        "run",
        MagicMock(
            side_effect=[
                *([None] * 6),
                subprocess.CalledProcessError(
                    returncode=1, cmd=[], output="", stderr="Failed to umount dev"
                ),
            ]
        ),
    )
    with pytest.raises(MountError) as exc:
        with ChrootContextManager(chroot_path=MagicMock()):
            pass

    assert "Failed to umount dev" in str(exc.getrepr())


def test_chroot_umount(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched subprocess run call that succeeds.
    act: when chroot context is exited.
    assert: no errors are raised.
    """
    monkeypatch.setattr(os, "chroot", MagicMock())
    monkeypatch.setattr(os, "chdir", MagicMock())
    monkeypatch.setattr(os, "fchdir", MagicMock())
    monkeypatch.setattr(os, "close", MagicMock())
    monkeypatch.setattr(subprocess, "run", MagicMock())
    with ChrootContextManager(chroot_path=MagicMock()):
        pass
