# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Exception raised by the builder."""


class BuilderBaseError(Exception):
    """Base exceptions for builder application."""


class DependencyInstallError(BuilderBaseError):
    """Represents an error while installing required dependencies."""


class ImageBuilderInstallError(BuilderBaseError):
    """Represents an error while installing github-runner-image-builder app."""


class BuilderSetupError(BuilderBaseError):
    """Represents an error while setting up host machine as builder."""


class ProxyInstallError(BuilderBaseError):
    """Represents an error while installing proxy."""


class GetLatestImageError(BuilderBaseError):
    """Represents an error while fetching the latest image."""
