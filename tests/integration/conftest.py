# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github runner charm integration tests."""
import os
import string
import time
from pathlib import Path
from typing import AsyncGenerator, NamedTuple, Optional

import openstack
import pytest
import pytest_asyncio
import yaml
from fabric.connection import Connection as SSHConnection
from juju.application import Application
from juju.model import Model
from openstack.compute.v2.image import Image
from openstack.compute.v2.keypair import Keypair
from openstack.connection import Connection
from pytest_operator.plugin import OpsTest

from openstack_manager import IMAGE_NAME_TMPL
from state import BASE_IMAGE_CONFIG_NAME, OPENSTACK_CLOUDS_YAML_CONFIG_NAME, _get_supported_arch
from tests.integration.helpers import wait_for_valid_connection


@pytest.fixture(scope="module", name="charm_file")
def charm_file_fixture(pytestconfig: pytest.Config) -> str:
    """Path to the built charm."""
    charm = pytestconfig.getoption("--charm-file")[0]
    assert charm, "Please specify the --charm-file command line option"
    return f"./{charm}"


@pytest_asyncio.fixture(scope="module", name="model")
async def model_fixture(ops_test: OpsTest) -> Model:
    """Juju model used in the test."""
    assert ops_test.model is not None

    # Set model proxy for the runners
    http_proxy = os.getenv("HTTP_PROXY", "")
    https_proxy = os.getenv("HTTPS_PROXY", "")
    await ops_test.model.set_config(
        {"juju-http-proxy": http_proxy, "juju-https-proxy": https_proxy}
    )
    return ops_test.model


@pytest_asyncio.fixture(scope="function", name="test_charm")
async def test_charm_fixture(ops_test: OpsTest, model: Model) -> AsyncGenerator[Application, None]:
    """The test charm that becomes active when valid relation data is given."""
    charm_file = await ops_test.build_charm("tests/integration/data/charm")
    app = await model.deploy(charm_file)
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


@pytest.fixture(scope="module", name="private_endpoint_clouds_yaml")
def private_endpoint_clouds_yaml_fixture(pytestconfig: pytest.Config) -> Optional[str]:
    """The openstack private endpoint clouds yaml."""
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
    return string.Template(
        Path("tests/integration/data/clouds.yaml.tmpl").read_text(encoding="utf-8")
    ).substitute(
        {
            "auth_url": auth_url,
            "password": password,
            "project_domain_name": project_domain_name,
            "project_name": project_name,
            "user_domain_name": user_domain_name,
            "username": user_name,
            "region_name": region_name,
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
    clouds_yaml_path.write_text(data=clouds_yaml, encoding="utf-8")
    first_cloud = next(iter(clouds_yaml["clouds"].keys()))
    return openstack.connect(first_cloud)


@pytest_asyncio.fixture(scope="module", name="app")
async def app_fixture(model: Model, charm_file: str, clouds_yaml_contents: str) -> Application:
    """The deployed application fixture."""
    app: Application = await model.deploy(
        charm_file,
        constraints="cores=3 mem=18G root-disk=15G virt-type=virtual-machine",
        config={OPENSTACK_CLOUDS_YAML_CONFIG_NAME: clouds_yaml_contents},
    )
    time.sleep(60 * 30)
    await model.wait_for_idle(
        apps=[app.name], wait_for_active=True, idle_period=30, timeout=40 * 60
    )
    return app


@pytest.fixture(scope="function", name="ssh_key")
def ssh_key_fixture(openstack_connection: Connection, tmp_path: Path):
    """The openstack ssh key fixture."""
    keypair: Keypair = openstack_connection.create_keypair("test-image-builder-keys")
    ssh_key_path = tmp_path / "tmp_key"
    ssh_key_path.touch(exist_ok=True)
    ssh_key_path.write_text(keypair.private_key, encoding="utf-8")

    yield keypair

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
    ssh_key: Keypair
    network: str
    flavor: str


@pytest.fixture(scope="function", name="openstack_metadata")
def openstack_metadata_fixture(
    openstack_connection: Connection, ssh_key: Keypair, network_name: str, flavor_name: str
) -> OpenstackMeta:
    """A wrapper around openstack related info."""
    return OpenstackMeta(
        connection=openstack_connection, ssh_key=ssh_key, network=network_name, flavor=flavor_name
    )


@pytest_asyncio.fixture(scope="function", name="ssh_connection")
async def ssh_connection_fixture(
    model: Model,
    app: Application,
    openstack_metadata: OpenstackMeta,
) -> AsyncGenerator[SSHConnection, None]:
    """The openstack server ssh connection fixture."""
    await model.wait_for_idle(apps=[app.name], wait_for_active=True, timeout=40 * 60)
    server_name = "test-server"

    # the config is the entire config info dict, weird.
    # i.e. {"name": ..., "description:", ..., "value":..., "default": ...}
    config: dict = await app.get_config()
    image_base = config[BASE_IMAGE_CONFIG_NAME]["value"]

    images: list[Image] = openstack_metadata.connection.search_images(
        IMAGE_NAME_TMPL.format(
            IMAGE_BASE=image_base, APP_NAME=app.name, ARCH=_get_supported_arch().value
        )
    )
    assert images, "No built image found."
    openstack_metadata.connection.create_server(
        name=server_name,
        image=images[0],
        key_name=openstack_metadata.ssh_key.name,
        # these are pre-configured values on private endpoint.
        flavor=openstack_metadata.flavor,
        network=openstack_metadata.network,
        timeout=120,
        wait=True,
    )

    ssh_connection = wait_for_valid_connection(
        connection=openstack_metadata.connection,
        server_name=server_name,
        network=openstack_metadata.network,
        ssh_key=openstack_metadata.ssh_key.name,
    )

    yield ssh_connection

    openstack_metadata.connection.delete_server(server_name)
