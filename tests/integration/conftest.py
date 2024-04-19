# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github runner charm integration tests."""
from pathlib import Path
from typing import Optional

import openstack
import pytest
import pytest_asyncio
import yaml
from juju.application import Application
from juju.model import Model
from openstack.compute.v2.keypair import Keypair
from openstack.connection import Connection
from pytest_operator.plugin import OpsTest

from state import OPENSTACK_CLOUDS_YAML_CONFIG_NAME


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


@pytest.fixture(scope="module", name="openstack_clouds_yaml")
def openstack_clouds_yaml_fixture(pytestconfig: pytest.Config) -> str:
    """Configured clouds-yaml setting."""
    clouds_yaml = pytestconfig.getoption("--openstack-clouds-yaml")
    assert clouds_yaml, "Please specify the --openstack-clouds-yaml command line option"
    return Path(clouds_yaml).read_text(encoding="utf-8")


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
        constraints="cores=2 mem=6G root-disk=15G virt-type=virtual-machine",
        config={OPENSTACK_CLOUDS_YAML_CONFIG_NAME: openstack_clouds_yaml},
    )
    await model.wait_for_idle(
        apps=[app.name], wait_for_active=True, idle_period=30, timeout=30 * 60
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
