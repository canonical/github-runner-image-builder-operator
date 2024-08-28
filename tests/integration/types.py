# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Types used in the integration test."""

import typing
from datetime import datetime
from pathlib import Path

from juju.model import Model
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
        arch: The architecture the test is running on.
        auth_url: OpenStack uthentication URL (Keystone).
        password: OpenStack password.
        project_domain_name: OpenStack project domain to use.
        project_name: OpenStack project to use within the domain.
        user_domain_name: OpenStack user domain to use.
        username: OpenStack user to use within the domain.
        region_name: OpenStack deployment region.
    """

    arch: typing.Literal["amd64", "arm64"]
    auth_url: str
    password: str
    project_domain_name: str
    project_name: str
    user_domain_name: str
    username: str
    region_name: str


class TestConfigs(typing.NamedTuple):
    """Test configuration values.

    Attributes:
        model: The juju test model.
        charm_file: The charm file path.
        dispatch_time: The test start time.
        test_id: The test unique identifier.
    """

    model: Model
    charm_file: str | Path
    dispatch_time: datetime
    test_id: str
