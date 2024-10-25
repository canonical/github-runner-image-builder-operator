# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Observer module for Jenkins to COS integration."""


import ops
from charms.grafana_agent.v0.cos_agent import COSAgentProvider


class Observer(ops.Object):
    """The Jenkins COS integration observer."""

    def __init__(self, charm: ops.CharmBase):
        """Initialize the observer and register event handlers.

        Args:
            charm: The parent charm to attach the observer to.
        """
        super().__init__(charm, "cos-observer")
        self._grafana_agent = COSAgentProvider(charm=charm)
