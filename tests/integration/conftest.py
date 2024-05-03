# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github runner charm integration tests."""
import os
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
    charm = pytestconfig.getoption("--charm-file")
    assert charm, "Please specify the --charm-file command line option"
    return f"./{charm}"


@pytest.fixture(scope="module", name="model")
def model_fixture(ops_test: OpsTest) -> Model:
    """Juju model used in the test."""
    assert ops_test.model is not None
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
def openstack_clouds_yaml_fixture() -> str:
    """Configured clouds-yaml setting."""
    # This secret is moved from INTEGRATION_TEST_ARGS secrets since GitHub does not mask
    # multiline secrets well and prints them on the log output.
    clouds_yaml = os.getenv("OPENSTACK_CLOUDS_YAML")
    assert clouds_yaml, "Please specify the OPENSTACK_CLOUDS_YAML environment variable."
    return clouds_yaml


@pytest.fixture(scope="module", name="network_name")
def network_name_fixture() -> str:
    """Network to use to spawn test instances under."""
    # This secret is moved from INTEGRATION_TEST_ARGS secrets since GitHub does not mask
    # multiline secrets well and prints them on the log output.
    network_name = os.getenv("OPENSTACK_NETWORK_NAME")
    assert network_name, "Please specify the OPENSTACK_NETWORK_NAME environment variable."
    return network_name


@pytest.fixture(scope="module", name="flavor_name")
def flavor_name_fixture() -> str:
    """Flavor to create testing instances with."""
    # This secret is moved from INTEGRATION_TEST_ARGS secrets since GitHub does not mask
    # multiline secrets well and prints them on the log output.
    flavor_name = os.getenv("OPENSTACK_FLAVOR_NAME")
    assert flavor_name, "Please specify the OPENSTACK_FLAVOR_NAME environment variable."
    return flavor_name


@pytest.fixture(scope="module", name="openstack_connection")
def openstack_connection_fixture(
    openstack_clouds_yaml: Optional[str],
) -> Connection:
    """The openstack connection instance."""
    assert openstack_clouds_yaml, "Openstack clouds yaml was not provided."

    openstack_clouds_yaml_yaml = yaml.safe_load(openstack_clouds_yaml)
    clouds_yaml_path = Path.cwd() / "clouds.yaml"
    clouds_yaml_path.write_text(data=openstack_clouds_yaml, encoding="utf-8")
    first_cloud = next(iter(openstack_clouds_yaml_yaml["clouds"].keys()))
    return openstack.connect(first_cloud)


@pytest_asyncio.fixture(scope="module", name="app")
async def app_fixture(model: Model, charm_file: str, openstack_clouds_yaml: str) -> Application:
    """The deployed application fixture."""
    app: Application = await model.deploy(
        charm_file,
        constraints="cores=2 mem=18G root-disk=15G virt-type=virtual-machine",
        config={OPENSTACK_CLOUDS_YAML_CONFIG_NAME: openstack_clouds_yaml},
    )
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
