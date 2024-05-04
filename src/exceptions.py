# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Exception raised by the builder."""


class BuilderBaseError(Exception):
    """Base exceptions for builder application."""


class GitProxyConfigError(BuilderBaseError):
    """Represents an error while configuring Git proxy."""
