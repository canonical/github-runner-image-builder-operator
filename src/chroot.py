# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Context manager for chrooting."""

import os
import subprocess
from pathlib import Path
from typing import Any, cast

CHROOT_DEVICE_DIR = "dev"
CHROOT_SHARED_DIRS = ["proc", "sys"]
CHROOT_EXTENDED_SHARED_DIRS = [*CHROOT_SHARED_DIRS, "dev"]


class ChrootBaseError(Exception):
    """Represents the errors with chroot."""


class MountError(ChrootBaseError):
    """Represents an error while (un)mounting shared dirs."""


class SyncError(ChrootBaseError):
    """Represents an error while syncing chroot dir."""


class ChrootContextManager:
    """A helper class for managing chroot environments."""

    def __init__(self, chroot_path: Path):
        """Initialize the chroot context manager.

        Args:
            chroot_path: The path to set as new root.
        """
        self.chroot_path = chroot_path
        self.root: None | int = None
        self.cwd: str = ""

    def __enter__(self) -> None:
        """Context enter for chroot.

        Raises:
            MountError: If there was an error mounting required shared directories.
        """
        self.root = os.open("/", os.O_PATH)
        self.cwd = os.getcwd()

        for shared_dir in CHROOT_EXTENDED_SHARED_DIRS:
            chroot_shared_dir = self.chroot_path / shared_dir
            try:
                subprocess.run(
                    ["mount", "--bind", f"/{shared_dir}", str(chroot_shared_dir)],
                    check=True,
                    timeout=30,
                )
            except subprocess.CalledProcessError as exc:
                raise MountError from exc
        os.chroot(self.chroot_path)
        os.chdir("/")

    def __exit__(self, *_args: Any, **_kwargs: Any) -> None:
        """Exit and unmount system dirs.

        Raises:
            MountError: if there was an error unmounting shared directories.
            SyncError: if there was an error syncing data.
        """
        os.chdir(cast(int, self.root))
        os.chroot(".")
        os.chdir(self.cwd)
        os.close(cast(int, self.root))

        try:
            subprocess.run(["sync"], check=True)
        except subprocess.CalledProcessError as exc:
            raise SyncError from exc

        for shared_dir in CHROOT_SHARED_DIRS:
            chroot_shared_dir = self.chroot_path / shared_dir
            try:
                subprocess.run(["umount", str(chroot_shared_dir)], check=True)
            except subprocess.CalledProcessError as exc:
                raise MountError from exc

        try:
            subprocess.run(["umount", "-l", str(self.chroot_path / CHROOT_DEVICE_DIR)], check=True)
        except subprocess.CalledProcessError as exc:
            raise MountError from exc
