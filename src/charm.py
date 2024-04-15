#!/usr/bin/env python3
# Copyright 2023 Mariyan Dimitrov
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

https://discourse.charmhub.io/t/4208
"""

import logging

import ops

import builder

logger = logging.getLogger(__name__)


class GithugRunnerImageBuilderCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self._on_install)

    def _on_install(self, _: ops.InstallEvent) -> None:
        """Handle installation of the charm.

        Installs apt packages required to build the image.
        """
        builder.install_dependencies()


if __name__ == "__main__":  # pragma: nocover
    ops.main(GithugRunnerImageBuilderCharm)
