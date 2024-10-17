# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Types used in the integration test."""

import dataclasses
import typing
from datetime import datetime
from pathlib import Path

from juju.model import Model
from openstack.compute.v2.keypair import Keypair
from openstack.connection import Connection
from openstack.network.v2.security_group import SecurityGroup


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


# The following is a wrapper for test related data and is not a duplicate code.
# pylint: disable=duplicate-code
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


# pylint: enable=duplicate-code


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


class ImageConfigs(typing.NamedTuple):
    """Image configuration values that are used for parametrized build.

    Attributes:
        bases: The Ubuntu OS Bases.
        juju_channels: The Juju snap channels to install.
        microk8s_channels: The Microk8s snap channels to install.
    """

    bases: tuple[str, ...]
    juju_channels: tuple[str, ...]
    microk8s_channels: tuple[str, ...]


class OpenstackMeta(typing.NamedTuple):
    """A wrapper around Openstack related info.

    Attributes:
        connection: The connection instance to Openstack.
        security_group: The OpenStack security group to create servers under.
        ssh_key: The SSH-Key created to connect to Openstack instance.
        network: The Openstack network to create instances under.
        flavor: The flavor to create instances with.
    """

    connection: Connection
    security_group: SecurityGroup
    ssh_key: SSHKey
    network: str
    flavor: str


@dataclasses.dataclass
class Commands:
    """Test commands to execute.

    Attributes:
        name: The test name.
        command: The command to execute.
        retry: number of times to retry.
    """

    name: str
    command: str
    retry: int = 1
