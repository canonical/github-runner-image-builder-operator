# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Context manager for chrooting."""

import os
import subprocess
from pathlib import Path

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

    def __enter__(self):
        """Context enter for chroot.

        Raises:
            MountError: If there was an error mounting required shared directories.
        """
        self.root = os.open("/", os.O_RDONLY)

        for dir in CHROOT_EXTENDED_SHARED_DIRS:
            chroot_shared_dir = self.chroot_path / dir
            chroot_shared_dir.mkdir(parents=True, exist_ok=True)
            root_shared_dir = Path(f"/{dir}")
            try:
                subprocess.run(
                    ["mount", "--bind", str(root_shared_dir), str(chroot_shared_dir)],
                    check=True,
                    timeout=30,
                )
            except subprocess.CalledProcessError as exc:
                raise MountError from exc
        os.chroot(self.chroot_path)

    def __exit__(self, *args, **kwargs):
        """Exit and unmount system dirs.

        Args:
            args: The placeholder for exit dundermethod args.
            kwargs: The placeholder for exit dundermethod kwargs.

        Raises:
            MountError: if there was an error unmounting shared directories.
            SyncError: if there was an error syncing data.
        """
        for dir in CHROOT_SHARED_DIRS:
            chroot_shared_dir = self.chroot_path / dir
            try:
                subprocess.run(["umount", str(chroot_shared_dir)])
            except subprocess.CalledProcessError as exc:
                raise MountError from exc

        try:
            subprocess.run("sync")
        except subprocess.CalledProcessError as exc:
            raise SyncError from exc
        os.fchdir(self.root)
        os.chroot(".")
        os.close(self.root)

        try:
            subprocess.run(["umount", "-l", str(self.chroot_path / CHROOT_DEVICE_DIR)])
        except subprocess.CalledProcessError as exc:
            raise MountError from exc
