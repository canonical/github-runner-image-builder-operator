# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Exception raised by the builder."""


class BuilderBaseError(Exception):
    """Base exceptions for builder application."""


class DependencyInstallError(BuilderBaseError):
    """Represents an error while installing required dependencies."""


class ImageBuilderInitializeError(BuilderBaseError):
    """Represents an error while initializing github-runner-image-builder app."""


class BuilderInitError(BuilderBaseError):
    """Represents an error while setting up host machine as builder."""


class BuilderRunError(BuilderBaseError):
    """Represents an error while running the image builder."""


class ProxyInstallError(BuilderBaseError):
    """Represents an error while installing proxy."""


class GetLatestImageError(BuilderBaseError):
    """Represents an error while fetching the latest image."""


class PipXError(Exception):
    """Represents an error while interacting with pipx."""
