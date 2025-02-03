# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github runner image builder integration tests."""
import logging
import os
import platform
import secrets
import string
import typing
import urllib.parse
from pathlib import Path

import openstack
import openstack.exceptions
import pytest
import yaml
from openstack.compute.v2.keypair import Keypair
from openstack.connection import Connection
from openstack.network.v2.security_group import SecurityGroup

from github_runner_image_builder import config
from tests.integration import types

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module", name="arch")
def arch_fixture():
    """The testing architecture."""
    arch = platform.machine()
    match arch:
        case arch if arch in config.ARCHITECTURES_ARM64:
            return config.Arch.ARM64
        case arch if arch in config.ARCHITECTURES_X86:
            return config.Arch.X64
    raise ValueError(f"Unsupported testing architecture {arch}")


@pytest.fixture(scope="module", name="test_id")
def test_id_fixture() -> str:
    """The random 2 char test id."""
    return "".join(secrets.choice(string.ascii_lowercase) for _ in range(2))


@pytest.fixture(scope="module", name="image")
def image_fixture(pytestconfig: pytest.Config) -> str:
    """The ubuntu image base to build from."""
    image = pytestconfig.getoption("--image")
    assert image, "Please specify the --image command line option"
    return image


@pytest.fixture(scope="module", name="image_config")
def image_config_fixture(arch: config.Arch, image: str):
    """The image related configuration parameters."""
    return types.ImageConfig(arch=arch, image=image)



@pytest.fixture(scope="module", name="private_endpoint_config")
def private_endpoint_config_fixture(
    pytestconfig: pytest.Config, arch: config.Arch
) -> types.PrivateEndpointConfig | None:
    """The OpenStack private endpoint configurations."""
    if arch == config.Arch.ARM64:
        auth_url = pytestconfig.getoption("--openstack-auth-url-arm64")
        password = os.getenv("OPENSTACK_PASSWORD_ARM64", "")
        project_domain_name = pytestconfig.getoption("--openstack-project-domain-name-arm64")
        project_name = pytestconfig.getoption("--openstack-project-name-arm64")
        user_domain_name = pytestconfig.getoption("--openstack-user-domain-name-arm64")
        user_name = pytestconfig.getoption("--openstack-username-arm64")
        region_name = pytestconfig.getoption("--openstack-region-name-arm64")
    else:
        auth_url = pytestconfig.getoption("--openstack-auth-url-amd64")
        password = os.getenv("OPENSTACK_PASSWORD_AMD64", "")
        project_domain_name = pytestconfig.getoption("--openstack-project-domain-name-amd64")
        project_name = pytestconfig.getoption("--openstack-project-name-amd64")
        user_domain_name = pytestconfig.getoption("--openstack-user-domain-name-amd64")
        user_name = pytestconfig.getoption("--openstack-username-amd64")
        region_name = pytestconfig.getoption("--openstack-region-name-amd64")
    if any(
        not val
        for val in (
            auth_url,
            password,
            project_domain_name,
            project_name,
            user_domain_name,
            user_name,
            region_name,
        )
    ):
        return None
    return types.PrivateEndpointConfig(
        auth_url=auth_url,
        password=password,
        project_domain_name=project_domain_name,
        project_name=project_name,
        user_domain_name=user_domain_name,
        username=user_name,
        region_name=region_name,
    )


@pytest.fixture(scope="module", name="clouds_yaml_contents")
def clouds_yaml_fixture(
    private_endpoint_config: types.PrivateEndpointConfig | None,
) -> typing.Optional[str]:
    """The openstack private endpoint clouds yaml."""
    if not private_endpoint_config:
        return None
    return string.Template(
        Path("tests/integration/data/clouds.yaml.tmpl").read_text(encoding="utf-8")
    ).substitute(
        {
            "auth_url": private_endpoint_config["auth_url"],
            "password": private_endpoint_config["password"],
            "project_domain_name": private_endpoint_config["project_domain_name"],
            "project_name": private_endpoint_config["project_name"],
            "user_domain_name": private_endpoint_config["user_domain_name"],
            "username": private_endpoint_config["username"],
            "region_name": private_endpoint_config["region_name"],
        }
    )


@pytest.fixture(scope="module", name="network_name")
def network_name_fixture(pytestconfig: pytest.Config, arch: config.Arch) -> str:
    """Network to use to spawn test instances under."""
    if arch == config.Arch.ARM64:
        network_name = pytestconfig.getoption("--openstack-network-name-arm64")
    else:
        network_name = pytestconfig.getoption("--openstack-network-name-amd64")
    assert network_name, "Please specify the --openstack-network-name command line option"
    return network_name


@pytest.fixture(scope="module", name="flavor_name")
def flavor_name_fixture(pytestconfig: pytest.Config, arch: config.Arch) -> str:
    """Flavor to create testing instances with."""
    if arch == config.Arch.ARM64:
        flavor_name = pytestconfig.getoption("--openstack-flavor-name-arm64")
    else:
        flavor_name = pytestconfig.getoption("--openstack-flavor-name-amd64")
    assert flavor_name, "Please specify the --openstack-flavor-name command line option"
    return flavor_name



@pytest.fixture(scope="module", name="cloud_name")
def cloud_name_fixture(clouds_yaml_contents: str) -> str:
    """The cloud to use from cloud config."""
    clouds_yaml = yaml.safe_load(clouds_yaml_contents)
    clouds_yaml_path = Path("clouds.yaml")
    clouds_yaml_path.write_text(data=clouds_yaml_contents, encoding="utf-8")
    first_cloud = next(iter(clouds_yaml["clouds"].keys()))
    return first_cloud


@pytest.fixture(scope="module", name="openstack_connection")
def openstack_connection_fixture(cloud_name: str) -> Connection:
    """The openstack connection instance."""
    return openstack.connect(cloud_name)


@pytest.fixture(scope="module", name="callback_result_path")
def callback_result_path_fixture() -> Path:
    """The file created when the callback script is run."""
    return Path("callback_complete")


@pytest.fixture(scope="module", name="callback_script")
def callback_script_fixture(callback_result_path: Path) -> Path:
    """The callback script to use with the image builder."""
    callback_script = Path("callback")
    callback_script.write_text(
        f"""#!/bin/bash
IMAGE_ID=$1
echo $IMAGE_ID | tee {callback_result_path}
""",
        encoding="utf-8",
    )
    callback_script.chmod(0o775)
    return callback_script


@pytest.fixture(scope="module", name="dockerhub_mirror")
def dockerhub_mirror_fixture(pytestconfig: pytest.Config) -> urllib.parse.ParseResult | None:
    """Dockerhub mirror URL."""
    dockerhub_mirror_url: str | None = pytestconfig.getoption("--dockerhub-mirror", default=None)
    if not dockerhub_mirror_url:
        return None
    parse_result = urllib.parse.urlparse(dockerhub_mirror_url)
    assert (
        parse_result.netloc and parse_result.port and parse_result.geturl()
    ), "Invalid dockerhub-mirror URL"
    return parse_result


@pytest.fixture(scope="module", name="openstack_image_name")
def openstack_image_name_fixture(test_id: str) -> str:
    """The image name to upload to openstack."""
    return f"image-builder-test-image-{test_id}"


@pytest.fixture(scope="module", name="ssh_key")
def ssh_key_fixture(
    openstack_connection: Connection, test_id: str
) -> typing.Generator[types.SSHKey, None, None]:
    """The openstack ssh key fixture."""
    keypair: Keypair = openstack_connection.create_keypair(f"test-image-builder-keys-{test_id}")
    ssh_key_path = Path("tmp_key")
    ssh_key_path.touch(exist_ok=True)
    ssh_key_path.write_text(keypair.private_key, encoding="utf-8")

    yield types.SSHKey(keypair=keypair, private_key=ssh_key_path)

    openstack_connection.delete_keypair(name=keypair.name)


@pytest.fixture(scope="module", name="openstack_metadata")
def openstack_metadata_fixture(
    openstack_connection: Connection,
    ssh_key: types.SSHKey,
    network_name: str,
    flavor_name: str,
    cloud_name: str,
) -> types.OpenstackMeta:
    """A wrapper around openstack related info."""
    return types.OpenstackMeta(
        connection=openstack_connection,
        cloud_name=cloud_name,
        ssh_key=ssh_key,
        network=network_name,
        flavor=flavor_name,
    )


@pytest.fixture(scope="module", name="openstack_security_group")
def openstack_security_group_fixture(openstack_connection: Connection):
    """An ssh-connectable security group."""
    security_group_name = "github-runner-image-builder-test-security-group"
    security_group: SecurityGroup | None = openstack_connection.get_security_group(
        name_or_id=security_group_name
    )
    if not security_group:
        security_group = openstack_connection.create_security_group(
            name=security_group_name,
            description="For servers managed by the github-runner-image-builder app.",
        )
        # For ping
        openstack_connection.create_security_group_rule(
            secgroup_name_or_id=security_group_name,
            protocol="icmp",
            direction="ingress",
            ethertype="IPv4",
        )
        # For SSH
        openstack_connection.create_security_group_rule(
            # The code is not duplicated, this code is strictly for integration test which should
            # not be imported from module or referenced from module.
            # pylint: disable=R0801
            secgroup_name_or_id=security_group_name,
            port_range_min="22",
            port_range_max="22",
            protocol="tcp",
            direction="ingress",
            ethertype="IPv4",
            # pylint: enable=R0801
        )
        # For tmate
        openstack_connection.create_security_group_rule(
            secgroup_name_or_id=security_group_name,
            port_range_min="10022",
            port_range_max="10022",
            protocol="tcp",
            direction="egress",
            ethertype="IPv4",
        )

    yield security_group

    openstack_connection.delete_security_group(security_group_name)


@pytest.fixture(scope="module", name="proxy")
def proxy_fixture(pytestconfig: pytest.Config) -> types.ProxyConfig:
    """The environment proxy to pass on to the charm/testing model."""

    # proxy has to be without http:// or https://  prefix
    if pytestconfig.getoption("--proxy"):
        proxy = pytestconfig.getoption("--proxy").removeprefix("http://").removeprefix("https://")
    else:
        proxy = None
    no_proxy = pytestconfig.getoption("--no-proxy")
    return types.ProxyConfig(http=proxy, https=proxy, no_proxy=no_proxy)
