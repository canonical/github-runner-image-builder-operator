# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module containing error definitions."""


class ImageBuilderBaseError(Exception):
    """Represents an error with any builder related executions."""


class BuilderInitializeError(ImageBuilderBaseError):
    """Represents an error while setting up host machine as builder."""


# nosec: B603: All subprocess runs are run with trusted executables.
class DependencyInstallError(BuilderInitializeError):
    """Represents an error while installing required dependencies."""


class NetworkBlockDeviceError(BuilderInitializeError):
    """Represents an error while enabling network block device."""


class UnsupportedArchitectureError(ImageBuilderBaseError):
    """Raised when given machine architecture is unsupported."""


class BuildImageError(ImageBuilderBaseError):
    """Represents an error while building the image."""


class UnmountBuildPathError(BuildImageError):
    """Represents an error while unmounting build path."""


class BaseImageDownloadError(BuildImageError):
    """Represents an error downloading base image."""


class ImageResizeError(BuildImageError):
    """Represents an error while resizing the image."""


class ImageConnectError(BuildImageError):
    """Represents an error while connecting the image to network block device."""


class ResizePartitionError(BuildImageError):
    """Represents an error while resizing network block device partitions."""


class UnattendedUpgradeDisableError(BuildImageError):
    """Represents an error while disabling unattended-upgrade related services."""


class SystemUserConfigurationError(BuildImageError):
    """Represents an error while adding user to chroot env."""


class PermissionConfigurationError(BuildImageError):
    """Represents an error while modifying dir permissions."""


class YQBuildError(BuildImageError):
    """Represents an error while building yq binary from source."""


class YarnInstallError(BuildImageError):
    """Represents an error installilng Yarn."""


class RunnerDownloadError(BuildImageError):
    """Represents an error downloading GitHub runner tar archive."""


class ImageCompressError(BuildImageError):
    """Represents an error while compressing cloud-img."""


class HomeDirectoryChangeOwnershipError(BuildImageError):
    """Represents an error while changing ubuntu home directory."""


class ExternalScriptError(BuildImageError):
    """Represents an error while running external script."""


class OpenstackBaseError(Exception):
    """Represents an error while interacting with Openstack."""


class UnauthorizedError(OpenstackBaseError):
    """Represents an unauthorized connection to Openstack."""


class UploadImageError(OpenstackBaseError):
    """Represents an error when uploading image to Openstack."""


class OpenstackError(OpenstackBaseError):
    """Represents an error while communicating with Openstack."""


class CloudsYAMLError(OpenstackBaseError):
    """Represents an error with clouds.yaml for OpenStack connection."""


class NotFoundError(OpenstackBaseError):
    """Represents an error with not matching OpenStack object found."""


class FlavorNotFoundError(NotFoundError):
    """Represents an error with given OpenStack flavor not found."""


class FlavorRequirementsNotMetError(NotFoundError):
    """Represents an error with given OpenStack flavor not meeting the minimum requirements."""


class NetworkNotFoundError(NotFoundError):
    """Represents an error with given OpenStack network not found."""


class AddressNotFoundError(OpenstackBaseError):
    """Represents an error with OpenStack instance not receiving an IP address."""


class CloudInitFailError(OpenstackBaseError):
    """Represents an error with cloud-init."""
