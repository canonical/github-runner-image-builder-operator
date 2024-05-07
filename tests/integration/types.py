# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Types used in the integration test."""

from pathlib import Path
from typing import NamedTuple

from openstack.compute.v2.keypair import Keypair


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


class SSHKey(NamedTuple):
    """Openstack SSH Keypair and private key.

    Attributes:
        keypair: OpenStach SSH Keypair object.
        private_key: The path to private key.
    """

    keypair: Keypair
    private_key: Path
