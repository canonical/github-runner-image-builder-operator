# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github runner charm integration tests."""
import functools
import logging
import platform
import secrets
import string

# subprocess module is used to call juju cli directly due to constraints with private-endpoint
# models
import subprocess  # nosec: B404
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Generator, Literal, Optional

import nest_asyncio
import openstack
import pytest
import pytest_asyncio
import yaml
from juju.application import Application
from juju.model import Model
from openstack.compute.v2.keypair import Keypair
from openstack.connection import Connection
from openstack.image.v2.image import Image
from openstack.network.v2.security_group import SecurityGroup
from pytest_operator.plugin import OpsTest

import state
from state import (
    APP_CHANNEL_CONFIG_NAME,
    BASE_IMAGE_CONFIG_NAME,
    BUILD_INTERVAL_CONFIG_NAME,
    EXTERNAL_BUILD_CONFIG_NAME,
    EXTERNAL_BUILD_FLAVOR_CONFIG_NAME,
    EXTERNAL_BUILD_NETWORK_CONFIG_NAME,
    JUJU_CHANNELS_CONFIG_NAME,
    OPENSTACK_AUTH_URL_CONFIG_NAME,
    OPENSTACK_PASSWORD_CONFIG_NAME,
    OPENSTACK_PROJECT_CONFIG_NAME,
    OPENSTACK_PROJECT_DOMAIN_CONFIG_NAME,
    OPENSTACK_USER_CONFIG_NAME,
    OPENSTACK_USER_DOMAIN_CONFIG_NAME,
    REVISION_HISTORY_LIMIT_CONFIG_NAME,
    _get_supported_arch,
)
from tests.integration.helpers import image_created_from_dispatch, wait_for
from tests.integration.types import (
    ImageConfigs,
    OpenstackMeta,
    PrivateEndpointConfigs,
    ProxyConfig,
    SSHKey,
    TestConfigs,
)

logger = logging.getLogger(__name__)

# This is required to dynamically load async fixtures in async def model_fixture()
nest_asyncio.apply()


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


@pytest.fixture(scope="module", name="arch")
def arch_fixture() -> Literal["amd64", "arm64"]:
    """The running test architecture."""
    arch = platform.machine()
    match arch:
        case arch if arch in state.ARCHITECTURES_ARM64:
            return "arm64"
        case arch if arch in state.ARCHITECTURES_X86:
            return "amd64"
    raise ValueError(f"Unsupported testing architecture {arch}")


@pytest.fixture(scope="module", name="use_private_endpoint")
def use_private_endpoint_fixture(
    pytestconfig: pytest.Config, arch: Literal["amd64", "arm64"]
) -> bool:
    """Whether the private endpoint is used."""
    openstack_auth_url = pytestconfig.getoption("--openstack-auth-url-arm64")
    # ARM64 requires private endpoint testing because we cannot test in LXD models due to nested
    # virtualization limitations.
    return bool(openstack_auth_url) and arch == "arm64"


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
        # await model.disconnect()
    else:
        # Dynamically use ops_test fixture - juju users on private endpoint do not have access to
        # the controller model and will fail. See issue:
        # https://github.com/juju/python-libjuju/issues/1064
        ops_test: OpsTest = request.getfixturevalue("ops_test")
        assert ops_test.model is not None
        # Check if private endpoint Juju model is being used. If not, configure proxy.
        # Note that "testing" is the name of the default testing model in operator-workflows.
        if "test" in ops_test.model.name:
            # Set model proxy for the runners
            await ops_test.model.set_config(
                {
                    "juju-http-proxy": proxy.http,
                    "juju-https-proxy": proxy.https,
                    "juju-no-proxy": proxy.no_proxy,
                }
            )
        yield ops_test.model


@pytest.fixture(scope="module", name="dispatch_time")
def dispatch_time_fixture():
    """The timestamp of the start of the charm tests."""
    return datetime.now(tz=timezone.utc)


@pytest_asyncio.fixture(scope="module", name="test_charm")
async def test_charm_fixture(
    model: Model,
    test_id: str,
    arch: Literal["amd64", "arm64"],
    private_endpoint_configs: PrivateEndpointConfigs,
) -> AsyncGenerator[Application, None]:
    """The test charm that becomes active when valid relation data is given."""
    # The predefine inputs here can be trusted
    subprocess.check_call(  # nosec: B603
        ["/snap/bin/charmcraft", "pack", "-p", "tests/integration/data/charm"]
    )
    logger.info("Deploying built test charm.")
    app_name = f"test-{test_id}"
    app: Application = await model.deploy(
        f"./test_ubuntu-22.04-{arch}.charm",
        app_name,
        config={
            "openstack-auth-url": private_endpoint_configs["auth_url"],
            "openstack-password": private_endpoint_configs["password"],
            "openstack-project-domain-name": private_endpoint_configs["project_domain_name"],
            "openstack-project-name": private_endpoint_configs["project_name"],
            "openstack-user-domain-name": private_endpoint_configs["user_domain_name"],
            "openstack-user-name": private_endpoint_configs["username"],
        },
    )

    yield app

    # logger.info("Cleaning up test charm.")
    # await model.remove_application(app_name=app_name, force=True, no_wait=True)
    # logger.info("Test charm removed.")


@pytest.fixture(scope="module", name="openstack_clouds_yaml")
def openstack_clouds_yaml_fixture(pytestconfig: pytest.Config) -> str:
    """Configured clouds-yaml setting."""
    clouds_yaml = pytestconfig.getoption("--openstack-clouds-yaml")
    return clouds_yaml


@pytest.fixture(scope="module", name="network_name")
def network_name_fixture(pytestconfig: pytest.Config, arch: Literal["amd64", "arm64"]) -> str:
    """Network to use to spawn test instances under."""
    network_name: str
    if arch == "arm64":
        network_name = pytestconfig.getoption("--openstack-network-name-arm64")
    else:
        network_name = pytestconfig.getoption("--openstack-network-name-amd64")
    assert network_name, "Please specify the --openstack-network-name(-amd64) command line option"
    return network_name


@pytest.fixture(scope="module", name="flavor_name")
def flavor_name_fixture(pytestconfig: pytest.Config, arch: Literal["amd64", "arm64"]) -> str:
    """Flavor to create testing instances with."""
    flavor_name: str
    if arch == "arm64":
        flavor_name = pytestconfig.getoption("--openstack-flavor-name-arm64")
    else:
        flavor_name = pytestconfig.getoption("--openstack-flavor-name-amd64")
    assert flavor_name, "Please specify the --openstack-flavor-name(-amd64) command line option"
    return flavor_name


@pytest.fixture(scope="module", name="private_endpoint_configs")
def private_endpoint_configs_fixture(
    pytestconfig: pytest.Config, arch: Literal["amd64", "arm64"]
) -> PrivateEndpointConfigs | None:
    """The OpenStack private endpoint configurations."""
    if arch == "arm64":
        auth_url = pytestconfig.getoption("--openstack-auth-url-arm64")
        password = pytestconfig.getoption("--openstack-password-arm64")
        project_domain_name = pytestconfig.getoption("--openstack-project-domain-name-arm64")
        project_name = pytestconfig.getoption("--openstack-project-name-arm64")
        user_domain_name = pytestconfig.getoption("--openstack-user-domain-name-arm64")
        user_name = pytestconfig.getoption("--openstack-username-arm64")
        region_name = pytestconfig.getoption("--openstack-region-name-arm64")
    else:
        auth_url = pytestconfig.getoption("--openstack-auth-url-amd64")
        password = pytestconfig.getoption("--openstack-password-amd64")
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
    return {
        "arch": arch,
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


@pytest.fixture(scope="module", name="dockerhub_mirror")
def dockerhub_mirror_fixture(pytestconfig: pytest.Config) -> str | None:
    """Dockerhub mirror URL."""
    return pytestconfig.getoption("--dockerhub-mirror")


@pytest.fixture(scope="module", name="test_id")
def test_id_fixture() -> str:
    """The test ID fixture."""
    return secrets.token_hex(4)


@pytest.fixture(scope="module", name="test_configs")
def test_configs_fixture(
    model: Model, charm_file: str, test_id: str, dispatch_time: datetime
) -> TestConfigs:
    """The test configuration values."""
    return TestConfigs(
        model=model, charm_file=charm_file, dispatch_time=dispatch_time, test_id=test_id
    )


@pytest.fixture(scope="module", name="image_configs")
def image_configs_fixture():
    """The image configuration values used to parametrize image build."""
    return ImageConfigs(
        bases=("jammy", "noble"),
        juju_channels=("3.5/stable",),
    )


@pytest_asyncio.fixture(scope="module", name="app")
async def app_fixture(
    test_configs: TestConfigs,
    private_endpoint_configs: PrivateEndpointConfigs,
    use_private_endpoint: bool,
    image_configs: ImageConfigs,
    openstack_metadata: OpenstackMeta,
) -> AsyncGenerator[Application, None]:
    """The deployed application fixture."""
    config = {
        APP_CHANNEL_CONFIG_NAME: "edge",
        BASE_IMAGE_CONFIG_NAME: ",".join(image_configs.bases),
        BUILD_INTERVAL_CONFIG_NAME: 12,
        JUJU_CHANNELS_CONFIG_NAME: ",".join(image_configs.juju_channels),
        REVISION_HISTORY_LIMIT_CONFIG_NAME: 5,
        OPENSTACK_AUTH_URL_CONFIG_NAME: private_endpoint_configs["auth_url"],
        OPENSTACK_PASSWORD_CONFIG_NAME: private_endpoint_configs["password"],
        OPENSTACK_PROJECT_CONFIG_NAME: private_endpoint_configs["project_name"],
        OPENSTACK_PROJECT_DOMAIN_CONFIG_NAME: private_endpoint_configs["project_domain_name"],
        OPENSTACK_USER_CONFIG_NAME: private_endpoint_configs["username"],
        OPENSTACK_USER_DOMAIN_CONFIG_NAME: private_endpoint_configs["user_domain_name"],
        EXTERNAL_BUILD_CONFIG_NAME: "True",
        EXTERNAL_BUILD_FLAVOR_CONFIG_NAME: openstack_metadata.flavor,
        EXTERNAL_BUILD_NETWORK_CONFIG_NAME: openstack_metadata.network,
    }
    base_machine_constraint = (
        f"arch={private_endpoint_configs['arch']} cores=4 mem=16G root-disk=50G"
    )
    # if local LXD testing model, make the machine of VM type
    if not use_private_endpoint:
        base_machine_constraint += " virt-type=virtual-machine"
    logger.info("Deploying image builder: %s", test_configs.dispatch_time)
    app: Application = await test_configs.model.deploy(
        test_configs.charm_file,
        application_name=f"image-builder-operator-{test_configs.test_id}",
        constraints=base_machine_constraint,
        config=config,
    )
    # This takes long due to having to wait for the machine to come up.
    await test_configs.model.wait_for_idle(apps=[app.name], idle_period=30, timeout=60 * 30)

    yield app

    # logger.info("Removing application.")
    # await test_configs.model.remove_application(app_name=app.name, force=True, no_wait=True)
    # logger.info("Application removed.")


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

    # logger.info("Cleaning up keypair.")
    # openstack_connection.delete_keypair(name=keypair.name)
    # logger.info("Keypair deleted.")


@pytest.fixture(scope="module", name="openstack_security_group")
def openstack_security_group_fixture(openstack_connection: Connection):
    """An ssh-connectable security group."""
    security_group_name = "github-runner-image-builder-operator-test-security-group"
    if security_groups := openstack_connection.search_security_groups(
        name_or_id=security_group_name
    ):
        yield security_groups[0]
        # for security_group in security_groups[1:]:
        #     openstack_connection.delete_security_group(name_or_id=security_group.id)
    else:
        security_group = openstack_connection.create_security_group(
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

        # logger.info("Cleaning up security group.")
        # openstack_connection.delete_security_group(security_group_name)
        # logger.info("Security group deleted.")


@pytest.fixture(scope="module", name="openstack_metadata")
def openstack_metadata_fixture(
    openstack_connection: Connection,
    ssh_key: SSHKey,
    network_name: str,
    flavor_name: str,
    openstack_security_group: SecurityGroup,
) -> OpenstackMeta:
    """A wrapper around openstack related info."""
    return OpenstackMeta(
        connection=openstack_connection,
        security_group=openstack_security_group,
        ssh_key=ssh_key,
        network=network_name,
        flavor=flavor_name,
    )


@pytest.fixture(scope="module", name="image_names")
def image_names_fixture(image_configs: ImageConfigs, app: Application):
    """Expected image names after imagebuilder run."""
    image_names = []
    arch = _get_supported_arch()
    for base in image_configs.bases:
        image_names.append(f"{app.name}-{base}-{arch.value}")
        for juju in image_configs.juju_channels:
            image_names.append(f"{app.name}-{base}-{arch.value}-juju-{juju.replace('/','-')}")
    return image_names


@pytest_asyncio.fixture(scope="module", name="bare_image_id")
async def bare_image_id_fixture(
    openstack_connection: Connection,
    dispatch_time: datetime,
    image_configs: ImageConfigs,
    app: Application,
):
    """The bare image expected from builder application."""
    arch = _get_supported_arch()
    image: Image | None = await wait_for(
        functools.partial(
            image_created_from_dispatch,
            image_name=f"{app.name}-{image_configs.bases[0]}-{arch.value}",
            connection=openstack_connection,
            dispatch_time=dispatch_time,
        ),
        timeout=60 * 30,
        check_interval=30,
    )
    assert image, "Bare image not found"
    return image.id


@pytest_asyncio.fixture(scope="module", name="juju_image_id")
async def juju_image_id_fixture(
    openstack_connection: Connection,
    dispatch_time: datetime,
    image_configs: ImageConfigs,
    app: Application,
):
    """The Juju bootstrapped image expected from builder application."""
    arch = _get_supported_arch()
    image: Image | None = await wait_for(
        functools.partial(
            image_created_from_dispatch,
            image_name=(
                f"{app.name}-{image_configs.bases[0]}-{arch.value}-juju-"
                f"{image_configs.juju_channels[0].replace('/','-')}"
            ),
            connection=openstack_connection,
            dispatch_time=dispatch_time,
        ),
        timeout=60 * 30,
        check_interval=30,
    )
    assert image, "Juju image not found"
    return image.id
