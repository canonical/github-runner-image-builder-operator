# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github runner charm integration tests."""
import logging
import secrets
import string
import subprocess
from pathlib import Path
from typing import AsyncGenerator, Generator, NamedTuple, Optional

import openstack
import pytest
import pytest_asyncio
import yaml
from fabric.connection import Connection as SSHConnection
from juju.application import Application
from juju.model import Model
from openstack.compute.v2.image import Image
from openstack.compute.v2.keypair import Keypair
from openstack.compute.v2.server import Server
from openstack.connection import Connection
from openstack.network.v2.security_group import SecurityGroup
from pytest_operator.plugin import OpsTest

from builder import IMAGE_NAME_TMPL
from state import (
    APP_CHANNEL_CONFIG_NAME,
    BASE_IMAGE_CONFIG_NAME,
    BUILD_INTERVAL_CONFIG_NAME,
    OPENSTACK_AUTH_URL_CONFIG_NAME,
    OPENSTACK_PASSWORD_CONFIG_NAME,
    OPENSTACK_PROJECT_CONFIG_NAME,
    OPENSTACK_PROJECT_DOMAIN_CONFIG_NAME,
    OPENSTACK_USER_CONFIG_NAME,
    OPENSTACK_USER_DOMAIN_CONFIG_NAME,
    REVISION_HISTORY_LIMIT_CONFIG_NAME,
    _get_supported_arch,
)
from tests.integration.helpers import get_juju_arch, wait_for_valid_connection
from tests.integration.types import PrivateEndpointConfigs, ProxyConfig, SSHKey

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module", name="charm_file")
def charm_file_fixture(pytestconfig: pytest.Config) -> str:
    """Path to the built charm."""
    charm = pytestconfig.getoption("--charm-file")[0]
    assert charm, "Please specify the --charm-file command line option"
    return f"./{charm}"


@pytest.fixture(scope="module", name="proxy")
def proxy_fixture(pytestconfig: pytest.Config) -> ProxyConfig:
    """The environment proxy to pass on to the charm/testing model."""
    proxy = pytestconfig.getoption("--proxy")
    no_proxy = pytestconfig.getoption("--no-proxy")
    return ProxyConfig(http=proxy, https=proxy, no_proxy=no_proxy)


@pytest.fixture(scope="module", name="use_private_endpoint")
def use_private_endpoint_fixture(pytestconfig: pytest.Config) -> bool:
    """Whether the private endpoint is used."""
    openstack_auth_url = pytestconfig.getoption("--openstack-auth-url")
    return bool(openstack_auth_url)


@pytest_asyncio.fixture(scope="module", name="model")
async def model_fixture(
    request: pytest.FixtureRequest, proxy: ProxyConfig, use_private_endpoint: bool
) -> AsyncGenerator[Model, None]:
    """Juju model used in the test."""
    model: Model
    if use_private_endpoint:
        model = Model()
        await model.connect()
        yield model
        await model.disconnect()
    else:
        ops_test: OpsTest = request.getfixturevalue("ops_test")
        assert ops_test.model is not None
        # Check if private endpoint Juju model is being used. If not, configure proxy.
        # Note that "testing" is the name of the default testing model in operator-workflows.
        if ops_test.model.name == "testing":
            # Set model proxy for the runners
            await ops_test.model.set_config(
                {
                    "juju-http-proxy": proxy.http,
                    "juju-https-proxy": proxy.https,
                    "juju-no-proxy": proxy.no_proxy,
                }
            )
        yield ops_test.model


@pytest_asyncio.fixture(scope="module", name="test_charm")
async def test_charm_fixture(model: Model) -> AsyncGenerator[Application, None]:
    """The test charm that becomes active when valid relation data is given."""
    build_cmd = ["charmcraft", "pack", "-p", "tests/integration/data/charm"]
    subprocess.check_call(build_cmd)
    app = await model.deploy(f"./test_ubuntu_22.04-{get_juju_arch()}.charm")
    await model.wait_for_idle(apps=[app.name])

    yield app

    await model.remove_application(app.name)


@pytest.fixture(scope="module", name="openstack_clouds_yaml")
def openstack_clouds_yaml_fixture(pytestconfig: pytest.Config) -> str:
    """Configured clouds-yaml setting."""
    clouds_yaml = pytestconfig.getoption("--openstack-clouds-yaml")
    return clouds_yaml


@pytest.fixture(scope="module", name="network_name")
def network_name_fixture(pytestconfig: pytest.Config) -> str:
    """Network to use to spawn test instances under."""
    network_name = pytestconfig.getoption("--openstack-network-name")
    assert network_name, "Please specify the --openstack-network-name command line option"
    return network_name


@pytest.fixture(scope="module", name="flavor_name")
def flavor_name_fixture(pytestconfig: pytest.Config) -> str:
    """Flavor to create testing instances with."""
    flavor_name = pytestconfig.getoption("--openstack-flavor-name")
    assert flavor_name, "Please specify the --openstack-flavor-name command line option"
    return flavor_name


@pytest.fixture(scope="module", name="private_endpoint_configs")
def private_endpoint_configs_fixture(pytestconfig: pytest.Config) -> PrivateEndpointConfigs | None:
    """The OpenStack private endpoint configurations."""
    auth_url = pytestconfig.getoption("--openstack-auth-url")
    password = pytestconfig.getoption("--openstack-password")
    project_domain_name = pytestconfig.getoption("--openstack-project-domain-name")
    project_name = pytestconfig.getoption("--openstack-project-name")
    user_domain_name = pytestconfig.getoption("--openstack-user-domain-name")
    user_name = pytestconfig.getoption("--openstack-user-name")
    region_name = pytestconfig.getoption("--openstack-region-name")
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
    return {
        "auth_url": auth_url,
        "password": password,
        "project_domain_name": project_domain_name,
        "project_name": project_name,
        "user_domain_name": user_domain_name,
        "username": user_name,
        "region_name": region_name,
    }


@pytest.fixture(scope="module", name="private_endpoint_clouds_yaml")
def private_endpoint_clouds_yaml_fixture(
    private_endpoint_configs: PrivateEndpointConfigs,
) -> Optional[str]:
    """The openstack private endpoint clouds yaml."""
    return string.Template(
        Path("tests/integration/data/clouds.yaml.tmpl").read_text(encoding="utf-8")
    ).substitute(
        {
            "auth_url": private_endpoint_configs["auth_url"],
            "password": private_endpoint_configs["password"],
            "project_domain_name": private_endpoint_configs["project_domain_name"],
            "project_name": private_endpoint_configs["project_name"],
            "user_domain_name": private_endpoint_configs["user_domain_name"],
            "username": private_endpoint_configs["username"],
            "region_name": private_endpoint_configs["region_name"],
        }
    )


@pytest.fixture(scope="module", name="clouds_yaml_contents")
def clouds_yaml_contents_fixture(
    openstack_clouds_yaml: Optional[str], private_endpoint_clouds_yaml: Optional[str]
):
    """The Openstack clouds yaml or private endpoint cloud yaml contents."""
    clouds_yaml_contents = openstack_clouds_yaml or private_endpoint_clouds_yaml
    assert clouds_yaml_contents, (
        "Please specify --openstack-clouds-yaml or all of private endpoint arguments "
        "(--openstack-auth-url, --openstack-password, --openstack-project-domain-name, "
        "--openstack-project-name, --openstack-user-domain-name, --openstack-user-name, "
        "--openstack-region-name)"
    )
    return clouds_yaml_contents


@pytest.fixture(scope="module", name="openstack_connection")
def openstack_connection_fixture(clouds_yaml_contents: str) -> Connection:
    """The openstack connection instance."""
    clouds_yaml = yaml.safe_load(clouds_yaml_contents)
    clouds_yaml_path = Path.cwd() / "clouds.yaml"
    clouds_yaml_path.write_text(data=clouds_yaml_contents, encoding="utf-8")
    first_cloud = next(iter(clouds_yaml["clouds"].keys()))
    return openstack.connect(first_cloud)


@pytest.fixture(scope="module", name="test_id")
def test_id_fixture() -> str:
    """The test ID fixture."""
    return secrets.token_hex(4)


@pytest_asyncio.fixture(scope="module", name="app")
async def app_fixture(
    model: Model, charm_file: str, test_id: str, private_endpoint_configs: PrivateEndpointConfigs
) -> Application:
    """The deployed application fixture."""
    config = {
        APP_CHANNEL_CONFIG_NAME: "edge",
        BUILD_INTERVAL_CONFIG_NAME: 12,
        REVISION_HISTORY_LIMIT_CONFIG_NAME: 2,
        OPENSTACK_AUTH_URL_CONFIG_NAME: private_endpoint_configs["auth_url"],
        OPENSTACK_PASSWORD_CONFIG_NAME: private_endpoint_configs["password"],
        OPENSTACK_PROJECT_CONFIG_NAME: private_endpoint_configs["project_name"],
        OPENSTACK_PROJECT_DOMAIN_CONFIG_NAME: private_endpoint_configs["project_domain_name"],
        OPENSTACK_USER_CONFIG_NAME: private_endpoint_configs["username"],
        OPENSTACK_USER_DOMAIN_CONFIG_NAME: private_endpoint_configs["user_domain_name"],
    }

    base_machine_constraint = f"arch={get_juju_arch()} cores=4 mem=16G root-disk=20G"
    # if local LXD testing model, make the machine of VM type
    if model == "testing":
        base_machine_constraint += " virt-type=virtual-machine"
    app: Application = await model.deploy(
        charm_file,
        application_name=f"image-builder-operator-{test_id}",
        constraints=base_machine_constraint,
        config=config,
    )
    # This takes long due to having to wait for the machine to come up.
    await model.wait_for_idle(
        apps=[app.name], wait_for_active=True, idle_period=30, timeout=60 * 30
    )
    return app


@pytest.fixture(scope="module", name="ssh_key")
def ssh_key_fixture(
    openstack_connection: Connection, test_id: str
) -> Generator[SSHKey, None, None]:
    """The openstack ssh key fixture."""
    keypair: Keypair = openstack_connection.create_keypair(
        f"test-image-builder-operator-keys-{test_id}"
    )
    ssh_key_path = Path("tmp_key")
    ssh_key_path.touch(exist_ok=True)
    ssh_key_path.write_text(keypair.private_key, encoding="utf-8")

    yield SSHKey(keypair=keypair, private_key=ssh_key_path)

    openstack_connection.delete_keypair(name=keypair.name)


class OpenstackMeta(NamedTuple):
    """A wrapper around Openstack related info.

    Attributes:
        connection: The connection instance to Openstack.
        ssh_key: The SSH-Key created to connect to Openstack instance.
        network: The Openstack network to create instances under.
        flavor: The flavor to create instances with.
    """

    connection: Connection
    ssh_key: SSHKey
    network: str
    flavor: str


@pytest.fixture(scope="module", name="openstack_metadata")
def openstack_metadata_fixture(
    openstack_connection: Connection, ssh_key: SSHKey, network_name: str, flavor_name: str
) -> OpenstackMeta:
    """A wrapper around openstack related info."""
    return OpenstackMeta(
        connection=openstack_connection, ssh_key=ssh_key, network=network_name, flavor=flavor_name
    )


@pytest.fixture(scope="module", name="openstack_security_group")
def openstack_security_group_fixture(openstack_connection: Connection):
    """An ssh-connectable security group."""
    security_group_name = "github-runner-image-builder-operator-test-security-group"
    security_group: SecurityGroup = openstack_connection.create_security_group(
        name=security_group_name,
        description="For servers managed by the github-runner charm.",
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
        secgroup_name_or_id=security_group_name,
        port_range_min="22",
        port_range_max="22",
        protocol="tcp",
        direction="ingress",
        ethertype="IPv4",
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


@pytest_asyncio.fixture(scope="module", name="openstack_server")
async def openstack_server_fixture(
    model: Model,
    app: Application,
    openstack_metadata: OpenstackMeta,
    openstack_security_group: SecurityGroup,
    test_id: str,
):
    """A testing openstack instance."""
    await model.wait_for_idle(apps=[app.name], wait_for_active=True, timeout=40 * 60)
    server_name = f"test-image-builder-operator-server-{test_id}"

    # the config is the entire config info dict, weird.
    # i.e. {"name": ..., "description:", ..., "value":..., "default": ...}
    config: dict = await app.get_config()
    image_base = config[BASE_IMAGE_CONFIG_NAME]["value"]

    images: list[Image] = openstack_metadata.connection.search_images(
        IMAGE_NAME_TMPL.format(IMAGE_BASE=image_base, ARCH=_get_supported_arch().value)
    )
    assert images, "No built image found."
    server: Server = openstack_metadata.connection.create_server(
        name=server_name,
        image=images[0],
        key_name=openstack_metadata.ssh_key.keypair.name,
        auto_ip=False,
        # these are pre-configured values on private endpoint.
        security_groups=[openstack_security_group.name],
        flavor=openstack_metadata.flavor,
        network=openstack_metadata.network,
        timeout=120,
        wait=True,
    )

    yield server

    openstack_metadata.connection.delete_server(server_name, wait=True)
    for image in images:
        openstack_metadata.connection.delete_image(image.id)


@pytest_asyncio.fixture(scope="module", name="ssh_connection")
async def ssh_connection_fixture(
    openstack_server: Server, openstack_metadata: OpenstackMeta, proxy: ProxyConfig
) -> SSHConnection:
    """The openstack server ssh connection fixture."""
    logger.info("Setting up SSH connection.")
    ssh_connection = wait_for_valid_connection(
        connection=openstack_metadata.connection,
        server_name=openstack_server.name,
        network=openstack_metadata.network,
        ssh_key=openstack_metadata.ssh_key.private_key,
        proxy=proxy,
    )

    return ssh_connection
