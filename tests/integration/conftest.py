# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github runner charm integration tests."""

import functools
import json
import logging
import multiprocessing
import os
import secrets
import string
import subprocess  # nosec
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional
from uuid import uuid4

import jubilant
import openstack
import pytest
import yaml
from openstack.compute.v2.keypair import Keypair
from openstack.connection import Connection
from openstack.image.v2.image import Image
from openstack.network.v2.security_group import SecurityGroup

import state
from state import (
    ARCHITECTURE_CONFIG_NAME,
    BASE_IMAGE_CONFIG_NAME,
    BUILD_INTERVAL_CONFIG_NAME,
    EXTERNAL_BUILD_FLAVOR_CONFIG_NAME,
    EXTERNAL_BUILD_NETWORK_CONFIG_NAME,
    OPENSTACK_AUTH_URL_CONFIG_NAME,
    OPENSTACK_PASSWORD_SECRET_CONFIG_NAME,
    OPENSTACK_PROJECT_CONFIG_NAME,
    OPENSTACK_PROJECT_DOMAIN_CONFIG_NAME,
    OPENSTACK_USER_CONFIG_NAME,
    OPENSTACK_USER_DOMAIN_CONFIG_NAME,
    REVISION_HISTORY_LIMIT_CONFIG_NAME,
    SCRIPT_URL_CONFIG_NAME,
)
from tests.integration.helpers import image_created_from_dispatch, wait_for
from tests.integration.types import (
    ImageConfigs,
    ImageVerificationContext,
    OpenstackMeta,
    PrivateEndpointConfigs,
    ProxyConfig,
    SSHKey,
    TestConfigs,
)

logger = logging.getLogger(__name__)

TEST_CHARM_FILE = "./test_ubuntu-22.04-amd64.charm"


@dataclass
class _Secret:
    """Data class for a secret.

    Attributes:
        id: The secret ID.
        name: The secret name.
    """

    id: str
    name: str


@dataclass
class CharmSecrets:
    """Juju secrets required by the charm.

    Attributes:
        script: The script secret.
        openstack_password: The OpenStack password secret.
    """

    script: _Secret
    openstack_password: _Secret


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


@pytest.fixture(scope="module", name="keep_models")
def keep_models_fixture(pytestconfig: pytest.Config) -> bool:
    """Whether to keep the testing models after tests complete."""
    return pytestconfig.getoption("--keep-models")


@pytest.fixture(scope="module", name="juju_ssh_key_path")
def juju_ssh_key_path_fixture() -> Path:
    """Path to the private SSH key used for juju ssh commands.

    Generates an RSA key pair at ~/.ssh/juju_id_rsa if it does not already
    exist, and returns the path to the private key.
    """
    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(mode=0o700, exist_ok=True)
    ssh_key_path = ssh_dir / "juju_id_rsa"
    if not ssh_key_path.exists():
        logger.info("Generating SSH key pair at %s", ssh_key_path)
        subprocess.run(  # nosec B603 B607
            ["ssh-keygen", "-t", "rsa", "-b", "4096", "-f", str(ssh_key_path), "-N", ""],
            check=True,
            capture_output=True,
        )
    return ssh_key_path


@pytest.fixture(scope="module", name="juju")
def juju_fixture(
    proxy: ProxyConfig,
    keep_models: bool,
    request: pytest.FixtureRequest,
    juju_ssh_key_path: Path,
) -> Generator[jubilant.Juju, None, None]:
    """Juju instance with a temporary model for testing."""
    with jubilant.temp_model(keep=keep_models) as juju:
        ssh_pub_key_path = juju_ssh_key_path.with_suffix(".pub")
        logger.info("Adding SSH public key to juju: %s", ssh_pub_key_path)
        juju.add_ssh_key(ssh_pub_key_path.read_text(encoding="utf-8"))
        if proxy.http:
            logger.info("Setting model proxy: %s", proxy.http)
            juju.model_config(
                {
                    "juju-http-proxy": proxy.http,
                    "juju-https-proxy": proxy.https,
                    "apt-http-proxy": proxy.http,
                    "apt-https-proxy": proxy.https,
                    "snap-http-proxy": proxy.http,
                    "snap-https-proxy": proxy.https,
                }
            )
        yield juju
        if request.session.testsfailed:
            log = juju.debug_log(limit=1000)
            print(log, end="")


@pytest.fixture(scope="module", name="dispatch_time")
def dispatch_time_fixture():
    """The timestamp of the start of the charm tests."""
    return datetime.now(tz=timezone.utc)


@pytest.fixture(scope="module", name="test_charm")
def test_charm_fixture(
    juju: jubilant.Juju,
    test_id: str,
    private_endpoint_configs: PrivateEndpointConfigs,
    openstack_password_secret: _Secret,
    keep_models: bool,
) -> Generator[str, None, None]:
    """The test charm that becomes active when valid relation data is given."""
    app_name = f"test-{test_id}"
    _deploy_test_charm(juju, app_name, private_endpoint_configs, openstack_password_secret)

    yield app_name

    if not keep_models:
        juju.remove_application(app_name)
        logger.info("Test charm application %s removed.", app_name)


@pytest.fixture(scope="module", name="test_charm_2")
def test_charm_2_fixture(
    juju: jubilant.Juju,
    test_id: str,
    private_endpoint_configs: PrivateEndpointConfigs,
    openstack_password_secret: _Secret,
    keep_models: bool,
) -> Generator[str, None, None]:
    """A second test charm that becomes active when valid relation data is given."""
    app_name = f"test2-{test_id}"
    _deploy_test_charm(juju, app_name, private_endpoint_configs, openstack_password_secret)

    yield app_name

    if not keep_models:
        logger.info("Cleaning up test charm.")
        juju.remove_application(app_name)
        logger.info("Test charm application %s removed.", app_name)


def _deploy_test_charm(
    juju: jubilant.Juju,
    app_name: str,
    private_endpoint_configs: PrivateEndpointConfigs,
    openstack_password_secret: _Secret,
) -> str:
    """Deploy the test charm with the given application name.

    Args:
        juju: The jubilant Juju instance.
        app_name: The name of the application to deploy.
        private_endpoint_configs: The OpenStack private endpoint configurations.
        openstack_password_secret: The juju secret containing the OpenStack password.

    Returns:
        The application name.
    """
    logger.info("Deploying built test charm")
    juju.deploy(
        TEST_CHARM_FILE,
        app_name,
        config={
            "openstack-auth-url": private_endpoint_configs["auth_url"],
            "openstack-password-secret": openstack_password_secret.id,
            "openstack-project-domain-name": private_endpoint_configs["project_domain_name"],
            "openstack-project-name": private_endpoint_configs["project_name"],
            "openstack-user-domain-name": private_endpoint_configs["user_domain_name"],
            "openstack-user-name": private_endpoint_configs["username"],
        },
        constraints={"virt-type": "virtual-machine"},
    )
    juju.grant_secret(openstack_password_secret.name, app_name)
    return app_name


@pytest.fixture(scope="module", name="arch")
def arch_fixture(pytestconfig: pytest.Config):
    """The testing architecture."""
    arch = pytestconfig.getoption("--arch")
    assert arch, "Please specify the --arch command line option"
    match arch:
        case "arm64":
            return state.Arch.ARM64
        case "amd64":
            return state.Arch.X64
        case "s390x":
            return state.Arch.S390X
        case "ppc64le":
            return state.Arch.PPC64LE
    raise ValueError(f"Unsupported testing architecture {arch}")


@pytest.fixture(scope="module", name="network_name")
def network_name_fixture(pytestconfig: pytest.Config) -> str:
    """Network to use to spawn test instances under."""
    network_name = pytestconfig.getoption("--openstack-network-name-amd64")
    assert network_name, "Please specify the --openstack-network-name(-amd64) command line option"
    return network_name


@pytest.fixture(scope="module", name="flavor_name")
def flavor_name_fixture(pytestconfig: pytest.Config) -> str:
    """Flavor to create testing instances with."""
    flavor_name = pytestconfig.getoption("--openstack-flavor-name-amd64")
    assert flavor_name, "Please specify the --openstack-flavor-name(-amd64) command line option"
    return flavor_name


@pytest.fixture(scope="module", name="private_endpoint_configs")
def private_endpoint_configs_fixture(pytestconfig: pytest.Config) -> PrivateEndpointConfigs | None:
    """The OpenStack private endpoint configurations."""
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
    return {
        "auth_url": auth_url,
        "password": password,
        "project_domain_name": project_domain_name,
        "project_name": project_name,
        "user_domain_name": user_domain_name,
        "username": user_name,
        "region_name": region_name,
    }


@pytest.fixture(scope="module", name="clouds_yaml_contents")
def clouds_yaml_fixture(
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


@pytest.fixture(scope="module", name="openstack_connection")
def openstack_connection_fixture(clouds_yaml_contents: str) -> Generator[Connection, None, None]:
    """The openstack connection instance."""
    clouds_yaml = yaml.safe_load(clouds_yaml_contents)
    clouds_yaml_path = Path.cwd() / "clouds.yaml"
    clouds_yaml_path.write_text(data=clouds_yaml_contents, encoding="utf-8")
    first_cloud = list(clouds_yaml["clouds"].keys())[0]
    with openstack.connect(first_cloud) as conn:
        yield conn


@pytest.fixture(scope="module", name="clean_up_resources", autouse=True)
def cleanup_resources_fixture(
    openstack_connection: Connection, image_names: list[str]
) -> Generator[None, None, None]:
    """Clean up resources after the tests are complete."""
    yield

    for image_name in image_names:
        for image in openstack_connection.search_images(name_or_id=image_name):
            openstack_connection.delete_image(image.id)


@pytest.fixture(scope="module", name="test_id")
def test_id_fixture() -> str:
    """The test ID fixture."""
    return secrets.token_hex(4)


@pytest.fixture(scope="module", name="test_configs")
def test_configs_fixture(
    juju: jubilant.Juju,
    charm_file: str,
    test_id: str,
    dispatch_time: datetime,
) -> TestConfigs:
    """The test configuration values."""
    return TestConfigs(
        juju=juju,
        charm_file=charm_file,
        dispatch_time=dispatch_time,
        test_id=test_id,
    )


@pytest.fixture(scope="module", name="image_configs")
def image_configs_fixture():
    """The image configuration values used to parametrize image build."""
    return ImageConfigs(
        bases=("noble",),
    )


@pytest.fixture(scope="module", name="script_secret")
def script_secret_fixture(juju: jubilant.Juju) -> _Secret:
    """The script secret."""
    secret_name = f"script-{uuid4().hex}"
    secret_uri = juju.add_secret(
        secret_name,
        {"testsecret": "TEST_VALUE"},
    )
    return _Secret(id=str(secret_uri), name=secret_name)


@pytest.fixture(scope="module", name="openstack_password_secret")
def openstack_password_secret_fixture(
    test_configs: TestConfigs,
    private_endpoint_configs: PrivateEndpointConfigs,
) -> _Secret:
    """The OpenStack password Juju secret."""
    secret_name = f"openstack-password-{uuid4().hex}"
    secret_uri = test_configs.juju.add_secret(
        secret_name,
        {"password": private_endpoint_configs["password"]},
    )
    return _Secret(id=str(secret_uri), name=secret_name)


@pytest.fixture(scope="module", name="charm_secrets")
def charm_secrets_fixture(
    script_secret: _Secret,
    openstack_password_secret: _Secret,
) -> CharmSecrets:
    """The Juju secrets required by the charm."""
    return CharmSecrets(script=script_secret, openstack_password=openstack_password_secret)


@pytest.fixture(scope="module", name="app_config")
def app_config_fixture(
    private_endpoint_configs: PrivateEndpointConfigs,
    image_configs: ImageConfigs,
    openstack_metadata: OpenstackMeta,
    arch: state.Arch,
    openstack_password_secret: _Secret,
) -> dict:
    """The image builder application config."""
    return {
        ARCHITECTURE_CONFIG_NAME: arch.value,
        BASE_IMAGE_CONFIG_NAME: ",".join(image_configs.bases),
        BUILD_INTERVAL_CONFIG_NAME: 12,
        REVISION_HISTORY_LIMIT_CONFIG_NAME: 5,
        OPENSTACK_AUTH_URL_CONFIG_NAME: private_endpoint_configs["auth_url"],
        OPENSTACK_PASSWORD_SECRET_CONFIG_NAME: openstack_password_secret.id,
        OPENSTACK_PROJECT_CONFIG_NAME: private_endpoint_configs["project_name"],
        OPENSTACK_PROJECT_DOMAIN_CONFIG_NAME: private_endpoint_configs["project_domain_name"],
        OPENSTACK_USER_CONFIG_NAME: private_endpoint_configs["username"],
        OPENSTACK_USER_DOMAIN_CONFIG_NAME: private_endpoint_configs["user_domain_name"],
        EXTERNAL_BUILD_FLAVOR_CONFIG_NAME: openstack_metadata.flavor,
        EXTERNAL_BUILD_NETWORK_CONFIG_NAME: openstack_metadata.network,
    }


@pytest.fixture(scope="module", name="base_machine_constraint")
def base_machine_constraint_fixture() -> dict:
    """The base machine constraint."""
    num_cores = max(1, multiprocessing.cpu_count() - 1)
    return {
        "arch": "amd64",
        "cores": num_cores,
        "mem": "4G",
        "root-disk": "20G",
        "virt-type": "virtual-machine",
    }


@pytest.fixture(scope="module", name="app")
def app_fixture(
    app_config: dict,
    base_machine_constraint: dict,
    test_configs: TestConfigs,
    charm_secrets: CharmSecrets,
    keep_models: bool,
) -> Generator[str, None, None]:
    """The deployed application fixture."""
    app_name = f"image-builder-operator-{test_configs.test_id}"
    logger.info("Deploying image builder: %s", test_configs.dispatch_time)
    test_configs.juju.deploy(
        test_configs.charm_file,
        app_name,
        constraints=base_machine_constraint,
        config=app_config,
    )
    test_configs.juju.grant_secret(charm_secrets.openstack_password.name, app_name)
    test_configs.juju.grant_secret(charm_secrets.script.name, app_name)
    test_configs.juju.config(
        app_name,
        {
            SCRIPT_URL_CONFIG_NAME: "https://raw.githubusercontent.com/canonical/"
            "github-runner-image-builder/refs/heads/main/tests/integration/"
            "testdata/test_script.sh",
            state.SCRIPT_SECRET_ID_CONFIG_NAME: charm_secrets.script.id,
        },
    )
    # This takes long due to having to wait for the machine to come up.
    test_configs.juju.wait(
        lambda s: jubilant.all_agents_idle(s, app_name),
        timeout=60 * 30,
    )

    yield app_name

    if not keep_models:
        test_configs.juju.remove_application(app_name)


def _prepare_charmhub_app_config(
    juju: jubilant.Juju, app_config: dict
) -> tuple[str, dict, set[str]]:
    """Prepare the application config for charmhub deployment.

    Args:
        juju: The jubilant Juju instance.
        app_config: The base application configuration.

    Returns:
        A tuple of (channel, prepared_config, config_options).

    """
    charmhub_channel = "edge"
    stdout = juju.cli(
        "info",
        "--format",
        "json",
        "--channel",
        charmhub_channel,
        "github-runner-image-builder",
        include_model=False,
    )
    charmhub_info = json.loads(stdout.strip())
    charmhub_config_options = set(charmhub_info["charm"]["config"]["Options"].keys())

    charmhub_app_config = {k: v for k, v in app_config.items() if k in charmhub_config_options}

    return charmhub_channel, charmhub_app_config, charmhub_config_options


@pytest.fixture(scope="module", name="app_on_charmhub")
def app_on_charmhub_fixture(
    test_configs: TestConfigs,
    app_config: dict,
    base_machine_constraint: dict,
    openstack_password_secret: _Secret,
    keep_models: bool,
) -> Generator[str, None, None]:
    """Fixture for deploying the charm from charmhub."""
    app_name = f"image-builder-charmhub-{test_configs.test_id}"
    # Normally we would use latest/stable, but upgrading
    # from stable is currently broken, and therefore we are using edge. Change this in the future.
    charmhub_channel, charmhub_app_config, charmhub_config_options = _prepare_charmhub_app_config(
        test_configs.juju, app_config
    )

    # Deploy without the secret-backed config so the charm doesn't try to read the secret
    # before the grant is in place.
    deploy_config = {
        k: v for k, v in charmhub_app_config.items() if k != OPENSTACK_PASSWORD_SECRET_CONFIG_NAME
    }
    test_configs.juju.deploy(
        "github-runner-image-builder",
        app_name,
        constraints=base_machine_constraint,
        config=deploy_config,
        channel=charmhub_channel,
    )
    test_configs.juju.wait(
        lambda s: jubilant.all_agents_idle(s, app_name),
        timeout=60 * 30,
    )

    if OPENSTACK_PASSWORD_SECRET_CONFIG_NAME in charmhub_config_options:
        # Grant access first, then set the config to trigger a config-changed hook
        # after the charm already has read permissions for the secret.
        test_configs.juju.grant_secret(openstack_password_secret.name, app_name)
        test_configs.juju.config(
            app_name, {OPENSTACK_PASSWORD_SECRET_CONFIG_NAME: openstack_password_secret.id}
        )

    test_configs.juju.wait(
        lambda s: jubilant.all_agents_idle(s, app_name),
        timeout=60 * 30,
    )

    yield app_name

    if not keep_models:
        test_configs.juju.remove_application(app_name)


@pytest.fixture(scope="module", name="ssh_key")
def ssh_key_fixture(
    openstack_connection: Connection, test_id: str
) -> Generator[SSHKey, None, None]:
    """The openstack ssh key fixture."""
    keypair: Keypair = openstack_connection.create_keypair(
        f"test-image-builder-operator-keys-{test_id}"
    )
    ssh_key_path = Path("testing_key.pem")
    ssh_key_path.touch(exist_ok=True)
    ssh_key_path.write_text(keypair.private_key, encoding="utf-8")

    yield SSHKey(keypair=keypair, private_key=ssh_key_path)

    logger.info("Cleaning up keypair.")
    openstack_connection.delete_keypair(name=keypair.name)
    logger.info("Keypair deleted.")


@pytest.fixture(scope="module", name="openstack_security_group")
def openstack_security_group_fixture(openstack_connection: Connection):
    """An ssh-connectable security group."""
    security_group_name = "github-runner-image-builder-operator-test-security-group"
    if security_groups := openstack_connection.search_security_groups(
        name_or_id=security_group_name
    ):
        yield security_groups[0]
        for security_group in security_groups[1:]:
            openstack_connection.delete_security_group(name_or_id=security_group.id)
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

        logger.info("Cleaning up security group.")
        openstack_connection.delete_security_group(security_group_name)
        logger.info("Security group deleted.")


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
def image_names_fixture(image_configs: ImageConfigs, app: str, arch: state.Arch):
    """Expected image names after imagebuilder run."""
    image_names = []
    for base in image_configs.bases:
        image_names.append(f"{app}-{base}-{arch.value}")
    return image_names


@pytest.fixture(scope="module", name="image_verification_context")
def image_verification_context_fixture(
    openstack_connection: Connection,
    image_names: list[str],
) -> ImageVerificationContext:
    """Context required to verify images built on OpenStack."""
    return ImageVerificationContext(
        openstack_connection=openstack_connection,
        image_names=image_names,
    )


@pytest.fixture(scope="module", name="bare_image_id")
def bare_image_id_fixture(
    openstack_connection: Connection,
    dispatch_time: datetime,
    image_configs: ImageConfigs,
    app: str,
    arch: state.Arch,
):
    """The bare image expected from builder application."""
    image: Image | None = wait_for(
        functools.partial(
            image_created_from_dispatch,
            image_name=f"{app}-{image_configs.bases[0]}-{arch.value}",
            connection=openstack_connection,
            dispatch_time=dispatch_time,
        ),
        timeout=60 * 30,
        check_interval=30,
    )
    assert image, "Bare image not found"
    return image.id
