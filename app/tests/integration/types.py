# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Types used in the integration test."""

import typing
from pathlib import Path

from openstack.compute.v2.keypair import Keypair
from openstack.connection import Connection

from github_runner_image_builder import config


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


class PrivateEndpointConfig(typing.TypedDict):
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


class OpenstackMeta(typing.NamedTuple):
    """A wrapper around Openstack related info.

    Attributes:
        connection: The connection instance to Openstack.
        cloud_name: The OpenStack cloud name to connect to.
        ssh_key: The SSH-Key created to connect to Openstack instance.
        network: The Openstack network to create instances under.
        flavor: The flavor to create instances with.
    """

    connection: Connection
    cloud_name: str
    ssh_key: SSHKey
    network: str
    flavor: str


class ImageConfig(typing.NamedTuple):
    """The image related configuration parameters.

    Attributes:
        arch: The architecture to build for.
        image: The ubuntu base image.
    """

    arch: config.Arch
    image: str
