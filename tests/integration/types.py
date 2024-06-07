# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Types used in the integration test."""

import typing
from pathlib import Path

from openstack.compute.v2.keypair import Keypair


class ProxyConfig(typing.NamedTuple):
    """Proxy configuration.

    Attributes:
        http: HTTP proxy address.
        https: HTTPS proxy address.
        no_proxy: Comma-separated list of hosts that should not be proxied.
    """

    http: str
    https: str
    no_proxy: str


class SSHKey(typing.NamedTuple):
    """Openstack SSH Keypair and private key.

    Attributes:
        keypair: OpenStach SSH Keypair object.
        private_key: The path to private key.
    """

    keypair: Keypair
    private_key: Path


class PrivateEndpointConfigs(typing.TypedDict):
    """The Private endpoint configuration values.

    Attributes:
        auth_url: OpenStack uthentication URL (Keystone).
        password: OpenStack password.
        project_domain_name: OpenStack project domain to use.
        project_name: OpenStack project to use within the domain.
        user_domain_name: OpenStack user domain to use.
        username: OpenStack user to use within the domain.
        region_name: OpenStack deployment region.
    """

    auth_url: str
    password: str
    project_domain_name: str
    project_name: str
    user_domain_name: str
    username: str
    region_name: str
