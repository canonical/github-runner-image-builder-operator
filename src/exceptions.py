# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Exception raised by the builder."""


class BuilderBaseError(Exception):
    """Base exceptions for builder application."""


class ImageBuilderInstallError(BuilderBaseError):
    """Represents an error while installing github-runner-image-builder app."""


class BuilderSetupError(Exception):
    """Represents an error while setting up host machine as builder."""


class BuildImageError(BuilderBaseError):
    """Represents an error while buildling an image."""


class ProxyInstallError(Exception):
    """Represents an error while installing proxy."""
