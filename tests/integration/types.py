# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Types used in the integration test."""

from typing import NamedTuple


class ProxyConfig(NamedTuple):
    """Proxy configuration.

    Attributes:
        http: HTTP proxy address.
        https: HTTPS proxy address.
        no_proxy: Comma-separated list of hosts that should not be proxied.
    """

    http: str
    https: str
    no_proxy: str
