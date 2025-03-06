# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for state module."""

# Need access to protected functions for testing, all tests are part of oepnstack_builder.py
# module.
# pylint:disable=protected-access,too-many-lines

import pathlib
import secrets
import typing
import urllib.parse
from unittest.mock import MagicMock

import paramiko
import paramiko.ssh_exception
import pytest
import tenacity
import yaml

from github_runner_image_builder import cloud_image, errors, openstack_builder, store


def test_determine_cloud_no_clouds_yaml_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched CLOUD_YAML_PATHS that returns no paths.
    act: when determine_cloud is called.
    assert: CloudsYAMLError is raised.
    """
    monkeypatch.setattr(openstack_builder, "CLOUD_YAML_PATHS", tuple())

    with pytest.raises(errors.CloudsYAMLError) as exc:
        openstack_builder.determine_cloud()

    assert "Unable to determine cloud to use" in str(exc)


def test_determine_cloud_clouds_yaml_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
):
    """
    arrange: given a monkeypatched CLOUD_YAML_PATHS that returns a test path.
    act: when determine_cloud is called.
    assert: CloudsYAMLError is raised.
    """
    test_clouds_yaml = tmp_path / "clouds.yaml"
    test_clouds_yaml.write_text("invalid content", encoding="utf-8")
    monkeypatch.setattr(
        openstack_builder, "CLOUD_YAML_PATHS", [tmp_path / "hello", test_clouds_yaml]
    )

    with pytest.raises(errors.CloudsYAMLError) as exc:
        openstack_builder.determine_cloud()

    assert "Invalid clouds.yaml" in str(exc)


def test_determine_cloud_user_input():
    """
    arrange: given a user input cloud_name.
    act: when determine_cloud is called.
    assert: cloud_name is returned.
    """
    test_cloud_name = "testcloud"
    assert openstack_builder.determine_cloud(test_cloud_name) == test_cloud_name


def test_determine_cloud(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path):
    """
    arrange: given monkeypatched clouds.yaml path.
    act: when determine_cloud is called.
    assert: correct cloud name is returned.
    """
    test_cloud_name = "testcloud"
    test_clouds_yaml = tmp_path / "clouds.yaml"
    test_clouds_yaml.write_text(
        yaml.safe_dump({"clouds": {test_cloud_name: {"auth": {}}}}), encoding="utf-8"
    )
    monkeypatch.setattr(openstack_builder, "CLOUD_YAML_PATHS", [test_clouds_yaml])

    assert openstack_builder.determine_cloud() == test_cloud_name


def test_initialize(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched cloud_image, store and openstack module functions.
    act: when initialize is called.
    assert: expected module calls are made.
    """
    monkeypatch.setattr(cloud_image, "download_and_validate_image", (download_mock := MagicMock()))
    monkeypatch.setattr(store, "upload_image", (upload_mock := MagicMock()))
    monkeypatch.setattr(openstack_builder.openstack, "connect", (connect_mock := MagicMock()))
    monkeypatch.setattr(openstack_builder, "_create_keypair", (create_keypair_mock := MagicMock()))
    monkeypatch.setattr(
        openstack_builder, "_create_security_group", (create_security_group_mock := MagicMock())
    )

    prefix = secrets.token_hex(8)
    openstack_builder.initialize(MagicMock(), MagicMock(), prefix=prefix)

    download_mock.assert_called()
    upload_mock.assert_called()
    assert prefix in upload_mock.call_args[1]["image_name"]
    connect_mock.assert_called()
    create_keypair_mock.assert_called()
    create_security_group_mock.assert_called()


def test__create_keypair_already_exists(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path):
    """
    arrange: given monkeypatched openstack connection with keys and mocked key path that exists.
    act: when _create_keypair is called.
    assert: create keypair functions are not called.
    """
    tmp_key_path = tmp_path / "test-key-path"
    tmp_key_path.touch(exist_ok=True)
    monkeypatch.setattr(openstack_builder, "BUILDER_KEY_PATH", tmp_key_path)
    connection_mock = MagicMock()

    openstack_builder._create_keypair(conn=connection_mock, prefix="")

    connection_mock.create_keypair.assert_not_called()


def test__create_keypair(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path):
    """
    arrange: given monkeypatched openstack connection with keys and mocked key path that exists.
    act: when _create_keypair is called.
    assert: create keypair functions are called.
    """
    test_key_path = tmp_path / "test_path"
    monkeypatch.setattr(openstack_builder, "BUILDER_KEY_PATH", test_key_path)
    monkeypatch.setattr(openstack_builder.shutil, "chown", MagicMock())
    connection_mock = MagicMock()
    connection_mock.get_keypair.return_value = None
    connection_mock.create_keypair.return_value = (mock_key := MagicMock())
    mock_key.private_key = "ssh-key-contents"

    openstack_builder._create_keypair(conn=connection_mock, prefix="")

    connection_mock.create_keypair.assert_called()
    assert tmp_path.exists()


def test__create_security_group_already_exists():
    """
    arrange: given a mocked openstack connection that returns a security group.
    act: when _create_security_group is called.
    assert: create functions are not called.
    """
    connection_mock = MagicMock()

    openstack_builder._create_security_group(conn=connection_mock)

    connection_mock.create_security_group.assert_not_called()


def test__create_security_group():
    """
    arrange: given a mocked openstack connection that returns no security group.
    act: when _create_security_group is called.
    assert: create functions not called.
    """
    connection_mock = MagicMock()
    connection_mock.get_security_group.return_value = False

    openstack_builder._create_security_group(conn=connection_mock)

    connection_mock.create_security_group.assert_called()


@pytest.mark.parametrize(
    "cloud_config",
    [
        pytest.param(
            openstack_builder.CloudConfig(
                cloud_name="test-cloud",
                flavor="test-flavor",
                network="test-network",
                prefix="",
                proxy="test-proxy",
                upload_cloud_names=[],
            ),
            id="no upload-cloud-name",
        ),
        pytest.param(
            openstack_builder.CloudConfig(
                cloud_name="test-cloud",
                flavor="test-flavor",
                network="test-network",
                prefix="",
                proxy="test-proxy",
                upload_cloud_names=["test-cloud-1"],
            ),
            id="single upload-cloud-name defined",
        ),
        pytest.param(
            openstack_builder.CloudConfig(
                cloud_name="test-cloud",
                flavor="test-flavor",
                network="test-network",
                prefix="",
                proxy="test-proxy",
                upload_cloud_names=["test-cloud-1", "test-cloud-2"],
            ),
            id="multiple upload-cloud-name defined",
        ),
    ],
)
def test_run(monkeypatch: pytest.MonkeyPatch, cloud_config: openstack_builder.CloudConfig):
    """
    arrange: given monkeypatched sub functions for openstack_builder.run.
    act: when run is called.
    assert: all subfunctions are called.
    """
    monkeypatch.setattr(
        openstack_builder, "_generate_cloud_init_script", (generate_cloud_init_mock := MagicMock())
    )
    monkeypatch.setattr(
        openstack_builder, "_prepare_openstack_resources", (ensure_resources_mock := MagicMock())
    )
    monkeypatch.setattr(
        openstack_builder, "_determine_flavor", (determine_flavor_mock := MagicMock())
    )
    monkeypatch.setattr(
        openstack_builder, "_determine_network", (determine_network_mock := MagicMock())
    )
    monkeypatch.setattr(store, "create_snapshot", create_image_snapshot := MagicMock())
    connection_enter_mock = MagicMock()
    connection_mock = MagicMock()
    connection_enter_mock.__enter__.return_value = connection_mock
    monkeypatch.setattr(
        openstack_builder.openstack,
        "connect",
        MagicMock(return_value=connection_enter_mock),
    )
    monkeypatch.setattr(
        openstack_builder, "_wait_for_cloud_init_complete", (wait_cloud_init_mock := MagicMock())
    )
    monkeypatch.setattr(
        openstack_builder, "_wait_for_snapshot_complete", (wait_snapshot_mock := MagicMock())
    )

    openstack_builder.run(
        cloud_config=cloud_config,
        image_config=MagicMock(),
        keep_revisions=5,
    )

    generate_cloud_init_mock.assert_called()
    ensure_resources_mock.assert_called()
    determine_flavor_mock.assert_called()
    determine_network_mock.assert_called()
    wait_cloud_init_mock.assert_called()
    wait_snapshot_mock.assert_called()
    create_image_snapshot.assert_called()
    connection_mock.create_server.assert_called()
    connection_mock.delete_server.assert_called()


def test__prepare_openstack_resources_invalid_resources(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched openstack functions that return invalid openstack state.
    act: when _prepare_openstack_resources is called.
    assert: recovery functions are called.
    """
    monkeypatch.setattr(openstack_builder, "_create_keypair", create_keypair_mock := MagicMock())
    monkeypatch.setattr(
        openstack_builder, "_create_security_group", create_security_group_mock := MagicMock()
    )
    connection_mock = MagicMock()
    connection_mock.get_keypair.return_value = None
    connection_mock.search_security_groups.return_value = [MagicMock(), MagicMock()]
    connection_mock.search_servers.return_value = [MagicMock(), MagicMock()]

    openstack_builder._prepare_openstack_resources(
        conn=connection_mock, builder_name="test", key_name="test", prefix="test"
    )

    create_keypair_mock.assert_called_once()
    create_security_group_mock.assert_called_once()
    connection_mock.delete_security_group.assert_called()
    connection_mock.delete_server.assert_called()


def test__prepare_openstack_resources(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given clean OpenStack resources state.
    act: when _prepare_openstack_resources is called.
    assert: no recovery functions are called.
    """
    monkeypatch.setattr(openstack_builder, "_create_keypair", create_keypair_mock := MagicMock())
    monkeypatch.setattr(
        openstack_builder,
        "_get_key_fingerprint",
        MagicMock(return_value=(fingerprint_mock := MagicMock())),
    )
    monkeypatch.setattr(
        openstack_builder, "_create_security_group", create_security_group_mock := MagicMock()
    )
    connection_mock = MagicMock()
    connection_mock.get_keypair.return_value = (keypair_mock := MagicMock())
    keypair_mock.fingerprint = fingerprint_mock
    connection_mock.search_security_groups.return_value = [MagicMock()]
    connection_mock.search_servers.return_value = []

    openstack_builder._prepare_openstack_resources(
        conn=connection_mock, builder_name="test", key_name="test", prefix="test"
    )

    create_keypair_mock.assert_not_called()
    create_security_group_mock.assert_not_called()
    connection_mock.delete_security_group.assert_not_called()
    connection_mock.delete_server.assert_not_called()


def test__get_key_fingerprint(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path):
    """
    arrange: given monkeypatched BUILDER_KEY_PATH that contains a mock ssh private key.
    act: when _get_key_fingerprint is called.
    assert: expected MD5 hash is generated.
    """
    test_key_file = tmp_path / "test-key"
    test_key_file.write_text(
        """-----BEGIN RSA PRIVATE KEY-----
MIIEogIBAAKCAQEAq95LRs57Vw5wq6YP7H0Dimw6zMVs8eMl86xyp938JG0bTXs3
ekyo5WH+QltDkLxBd8PInjUcHwEeci8+4dQq5JwTSX/2rgHKhoEX3ePDlohRbLpR
ccaIPbFcIoNSqaZ8nuO37zwcbNWVv6BJlYdMlPVyPaGclAvN7NDpqHeV7b5JtOGU
lZOS/DbsKqCXNBpiqUsqRAaBSGF8yvEnoJSHtrTTN9HkPW1Ssf8NfCo4X3V+/E2v
7eUdAuu7buCRZ3W0qaez7Et3I0Zktp8fDXFdo30eZ+qXUU7hrai52Se7TGQ6iTGO
fbAgGMdtbEReuXMxRUGBYwIeYQodtQ+yyirVPwIDAQABAoIBABJJjOjz1NvmhXE+
Mjjk9G4o0KOJPkEJUmMjLkVTsXM5c3ZDGMbCnBYMNJRgRvLXlSpmgqo9gciAGKU9
sbXbGtVIZiT5S14ogqGH4D+T70kifXIm675CHwJcJNmR75xtl++wJe98Deo8BRBm
wG2l/9gPEHYjrsLHSW9cAKtpo2JbIu76MyHbVk7TGQ7Rnho6cNvM/dM1IL3S2Jgd
3wjEQIDia+k57lImm+czkkvKUd/geAkx+Qv6ngUVpdIrBoG0iccFvKQK3+hWQ3e6
VEf2Up+LAh/gtpVsNwQLwEsJ+o1VjmTNhGHEjJjzi7tCwf/xKXy4q78jtpbIatCr
xUrQgIECgYEA4HMyzl+R82uIfQ99CewRw4SzSpfevnFVavOr7hq+s9J5S0Va52lM
pBxPtyxKovd8dinIqdb9rufmxqR4+FTRpQb1hLZ/HVJ1f79jwhmrln2WxP4hiVB+
02C0apnx9AVDlVuRuRUe1vZ2LwpgUyNVUulX+PvlnDk7YAf52UcF43kCgYEAxAbz
tspHOMrHyygPmJgX4Mxei2BGWw8bsX/nqqS/der6Wf9eVZGrqz0bjlUWluRQQ3/S
LpiUokujJgoauWafVQLyRSvtr7/ATt2p7+i2aT7aPys5GuVlk7lrlZTJTKNwr5EK
sYGxW6Fhz+aYqtz5ykUe957Vnd3ViPe8DiKA2HcCgYBR7XrUHcp2of/WNnsbzhHF
3oBbcAgcV94oBf3yEc0ecmtX8F74LVWOac8nO4Ga7t99ek8Gv7UlzPxN8ec+LifA
J0QjR0Iq/9hn4wKU7S3W5szL5z9ykfFZUulIKB1LR0ieEiik+HKjYJ9PGGiEsFcK
xqYX+kqbtcBYk1C94NDjcQKBgBPAz5Y/0+V5KaDjLI8n5GAWuAA7d1t9rkC4rtOX
PmPXhdrDzPG6eB4NTlWNZXVXFG941ek0HuYr0QjoQ8EjAjNC1L77qjvniq1n0NQI
EzmPx9ZNuLdpHk9AhALSt2YtohFPAFDazNB69qxIhGHTWqhzRqeVLdl2nSnsLNsP
xwQJAoGAWaindsaPPdeUr4aXdaSh9qMo9vTaa6xACUtd+qXdNtttlvyqlj6yTee+
z5AZpo2vLdDTnDt8AN/szyWAHpvhKlZc35fxYLaXWHbDylIhmG/Zaw/jxc8kMyKl
JRUbu09rVwHu50zKZ8CHhqXTnA9E2b295H9H1QPRR6qvQb2jjlc=
-----END RSA PRIVATE KEY-----""",
        encoding="utf-8",
    )
    monkeypatch.setattr(openstack_builder, "BUILDER_KEY_PATH", test_key_file)

    assert (
        openstack_builder._get_key_fingerprint()
        == "e0:6c:37:7e:d6:f5:a7:7d:b7:bc:5d:27:ac:4c:8a:18"
    )


def test__determine_flavor_flavor_not_found():
    """
    arrange: given a mocked openstack connection instance that returns no flavors.
    act: when _determine_flavor is called.
    assert: FlavorNotFoundError is raised.
    """
    mock_connection = MagicMock()
    mock_connection.get_flavor.return_value = None
    test_flavor_name = "test-flavor"

    with pytest.raises(errors.FlavorNotFoundError) as exc:
        openstack_builder._determine_flavor(conn=mock_connection, flavor_name=test_flavor_name)

    assert f"Given flavor {test_flavor_name} not found." in str(exc)


def test__determine_flavor_no_flavor():
    """
    arrange: given a mocked openstack connection instance that returns no flavors.
    act: when _determine_flavor is called.
    assert: FlavorNotFoundError is raised.
    """
    mock_connection = MagicMock()
    mock_connection.list_flavors.return_value = []

    with pytest.raises(errors.FlavorNotFoundError) as exc:
        openstack_builder._determine_flavor(conn=mock_connection, flavor_name=None)

    assert "No suitable flavor found" in str(exc)


class Flavor(typing.NamedTuple):
    """Test flavor type.

    Attributes:
        name: The flavor name.
        id: The flavor id.
        vcpus: Number of CPUs.
        ram: Memory size in M.
        disk: Disk size in M.
    """

    name: str
    id: str
    vcpus: int
    disk: int
    ram: int


def test__determine_flavor_min_requirements_not_met():
    """
    arrange: given a mocked openstack connection instance that returns flavors with matching name \
        but not matching the minimum requirements.
    act: when _determine_flavor is called with a name.
    assert: FlavorRequirementsNotMetError is raised.
    """
    mock_connection = MagicMock()
    mock_connection.get_flavor = MagicMock(
        return_value=(
            test_flavor := Flavor(name="test-flavor", id="test-id", vcpus=2, disk=2, ram=2)
        )
    )

    with pytest.raises(errors.FlavorRequirementsNotMetError) as exc:
        openstack_builder._determine_flavor(conn=mock_connection, flavor_name=test_flavor.name)

    assert "does not meet the minimum requirements" in str(exc)


@pytest.mark.parametrize(
    "flavors, name, expected_flavor",
    [
        pytest.param(
            (
                Flavor("test-flavor-1", "1", 1, 10, 8192),
                Flavor("test-flavor-2", "2", 2, 30, 8192),
                Flavor("test-flavor-2", "2", 8, 80, 16000),
            ),
            None,
            Flavor("test-flavor-2", "2", 2, 30, 8192),
            id="min flavor",
        ),
        pytest.param(
            (Flavor("test-flavor-1", "1", 1, 10, 8192), Flavor("test-flavor-2", "2", 4, 30, 8192)),
            "test-flavor-2",
            Flavor("test-flavor-2", "2", 4, 30, 8192),
            id="matching name",
        ),
    ],
)
def test__determine_flavor(
    flavors: typing.Iterable[Flavor], name: str | None, expected_flavor: Flavor
):
    """
    arrange: given a mocked openstack connection instance that returns parametrized flavors.
    act: when _determine_flavor is called.
    assert: the smallest matching flavor is selected.
    """
    mock_connection = MagicMock()
    mock_connection.get_flavor = MagicMock(return_value=expected_flavor)
    mock_connection.list_flavors.return_value = flavors

    assert (
        openstack_builder._determine_flavor(conn=mock_connection, flavor_name=name)
        == expected_flavor.id
    )


def test__determine_network_no_network():
    """
    arrange: given a mock get_network() command that returns no networks.
    act: when _determine_network is called.
    assert: NetworkNotFoundError error is raised.
    """
    mock_connection = MagicMock()
    mock_connection.get_network.return_value = None
    test_network_name = "test-network-name"

    with pytest.raises(errors.NetworkNotFoundError) as exc:
        openstack_builder._determine_network(conn=mock_connection, network_name=test_network_name)

    assert f"Given network {test_network_name} not found." in str(exc)


def test__determine_network_no_subnet():
    """
    arrange: given a mock list_subnets() command that returns no subnets.
    act: when _determine_network is called.
    assert: NetworkNotFoundError error is raised.
    """
    mock_connection = MagicMock()
    mock_connection.list_subnets.return_value = []

    with pytest.raises(errors.NetworkNotFoundError) as exc:
        openstack_builder._determine_network(conn=mock_connection, network_name=None)

    assert "No valid subnets found" in str(exc)


class Subnet(typing.NamedTuple):
    """Test subnet dataclass.

    Attributes:
        id: The subnet ID.
    """

    id: str


class Network(typing.NamedTuple):
    """Test network dataclass.

    Attributes:
        name: The network name
        id: The network ID
        subnet_ids: The subnets IDs under network.
    """

    name: str
    id: str
    subnet_ids: list[str]


def test__determine_network_no_networks():
    """
    arrange: given a mock list_networks() command that returns no networks.
    act: when _determine_network is called.
    assert: NetworkNotFoundError error is raised.
    """
    mock_connection = MagicMock()
    mock_connection.list_networks.return_value = []
    mock_connection.list_subnets.return_value = [Subnet("test-subnet-id")]

    with pytest.raises(errors.NetworkNotFoundError) as exc:
        openstack_builder._determine_network(conn=mock_connection, network_name=None)

    assert "No suitable network found" in str(exc)


@pytest.mark.parametrize(
    "network_name",
    [
        pytest.param(None, id="auto detect"),
        pytest.param("test-network-name", id="use existing"),
    ],
)
def test__determine_network(network_name: str | None):
    """
    arrange: given a mock mock list_networks and list_networks command that return valid networks.
    act: when _determine_network is called.
    assert: corresponding network is returned.
    """
    mock_network = MagicMock()
    mock_network.id = "test-network-id"
    mock_connection = MagicMock()
    mock_connection.get_network = MagicMock(return_value=mock_network)
    subnet = Subnet("test-subnet-id")
    mock_connection.list_networks.return_value = [
        Network("test-network-not-target", "test-network-not-target-id", []),
        Network("test-network-name", "test-network-id", [subnet.id]),
    ]
    mock_connection.list_subnets.return_value = [subnet]

    assert (
        openstack_builder._determine_network(conn=mock_connection, network_name=network_name)
        == "test-network-id"
    )


# TODO: Debug: removed gh for now.
def test__generate_cloud_init_script():
    """
    arrange: None.
    act: when _generate_cloud_init_script is run.
    assert: cloud init template is generated.
    """
    assert (
        openstack_builder._generate_cloud_init_script(
            image_config=openstack_builder.config.ImageConfig(
                arch=openstack_builder.Arch.X64,
                base=openstack_builder.BaseImage.JAMMY,
                runner_version="",
                name="test-image",
                script_config=openstack_builder.config.ScriptConfig(
                    script_url=urllib.parse.urlparse("https://test-url.com/script.sh"),
                    script_secrets={"TEST_SECRET_ONE": "HELLO", "TEST_SECRET_TWO": "WORLD"},
                ),
            ),
            proxy="test.proxy.internal:3128",
        )
        # The templated script contains similar lines to helper for setting up proxy.
        # pylint: disable=R0801
        == """#!/bin/bash

set -e

hostnamectl set-hostname github-runner

function configure_proxy() {
    local proxy="$1"
    if [[ -z "$proxy" ]]; then
        return
    fi
    echo "Installing aproxy"
    /usr/bin/sudo snap install aproxy --edge;
    /usr/bin/sudo nft -f - << EOF
define default-ip = $(ip route get $(ip route show 0.0.0.0/0 | grep -oP 'via \\K\\S+') | grep -oP \
'src \\K\\S+')
define private-ips = { 10.0.0.0/8, 127.0.0.1/8, 172.16.0.0/12, 192.168.0.0/16 }
table ip aproxy
flush table ip aproxy
table ip aproxy {
        chain prerouting {
                type nat hook prerouting priority dstnat; policy accept;
                ip daddr != \\$private-ips tcp dport { 80, 443 } counter dnat to \\$default-ip:8444
        }
        chain output {
                type nat hook output priority -100; policy accept;
                ip daddr != \\$private-ips tcp dport { 80, 443 } counter dnat to \\$default-ip:8444
        }
}
EOF
    echo "Configuring aproxy"
    /usr/bin/sudo snap set aproxy proxy=${proxy} listen=:8444;
    echo "Wait for aproxy to start"
    sleep 5
}

function install_apt_packages() {
    local packages="$1"
    local hwe_version="$2"
    echo "Updating apt packages"
    DEBIAN_FRONTEND=noninteractive /usr/bin/apt-get update -y
    echo "Installing apt packages $packages"
    DEBIAN_FRONTEND=noninteractive /usr/bin/apt-get install -y --no-install-recommends ${packages}
    echo "Installing linux-generic-hwe-${hwe_version}"
    DEBIAN_FRONTEND=noninteractive /usr/bin/apt-get install -y --install-recommends \
linux-generic-hwe-${hwe_version}
}

function disable_unattended_upgrades() {
    echo "Disabling unattended upgrades"
    /usr/bin/systemctl disable apt-daily.timer
    /usr/bin/systemctl disable apt-daily.service
    /usr/bin/systemctl disable apt-daily-upgrade.timer
    /usr/bin/systemctl disable apt-daily-upgrade.service
    /usr/bin/apt-get remove -y unattended-upgrades
}

function enable_network_fair_queuing_congestion() {
    /usr/bin/cat <<EOF | /usr/bin/sudo /usr/bin/tee -a /etc/sysctl.conf
net.core.default_qdisc=fq
net.ipv4.tcp_congestion_control=bbr
EOF
    /usr/sbin/sysctl -p
}

function configure_usr_local_bin() {
    echo "Configuring /usr/local/bin path"
    /usr/bin/chmod 777 /usr/local/bin
}

function install_yarn() {
    echo "Installing yarn"
    /usr/bin/npm install --global yarn
    /usr/bin/npm cache clean --force
}

function install_yq() {
    /usr/bin/sudo -E /usr/bin/snap install go --classic
    /usr/bin/sudo -E /usr/bin/git clone https://github.com/mikefarah/yq.git
    /usr/bin/sudo -E /snap/bin/go mod tidy -C yq
    /usr/bin/sudo -E /snap/bin/go build -C yq -o /usr/bin/yq
    /usr/bin/sudo -E /usr/bin/rm -rf yq
    /usr/bin/sudo -E /usr/bin/snap remove go
}

function install_github_runner() {
    version="$1"
    arch="$2"
    echo "Installing GitHub runner"
    if [[ -z "$version" ]]; then
        # Follow redirectin to get latest version release location
        # e.g. https://github.com/actions/runner/releases/tag/v2.318.0
        location=$(curl -sIL "https://github.com/actions/runner/releases/latest" | sed -n \
's/^location: *//p' | tr -d '[:space:]')
        # remove longest prefix from the right that matches the pattern */v
        # e.g. 2.318.0
        version=${location##*/v}
    fi
    /usr/bin/wget "https://github.com/actions/runner/releases/download/v$version/\
actions-runner-linux-$arch-$version.tar.gz"
    /usr/bin/mkdir -p /home/ubuntu/actions-runner
    /usr/bin/tar -xvzf "actions-runner-linux-$arch-$version.tar.gz" --directory \
/home/ubuntu/actions-runner

    rm "actions-runner-linux-$arch-$version.tar.gz"
}

function chown_home() {
    /usr/bin/chown --recursive ubuntu:ubuntu /home/ubuntu/
}

function configure_system_users() {
    echo "Configuring ubuntu user"
    # only add ubuntu user if ubuntu does not exist
    /usr/bin/id -u ubuntu &>/dev/null || useradd --create-home ubuntu
    echo "PATH=\\$PATH:/home/ubuntu/.local/bin" >> /home/ubuntu/.profile
    echo "PATH=\\$PATH:/home/ubuntu/.local/bin" >> /home/ubuntu/.bashrc
    /usr/sbin/groupadd -f microk8s
    /usr/sbin/groupadd -f docker
    /usr/sbin/usermod --append --groups docker,microk8s,lxd,sudo ubuntu
}

function execute_script() {
    local script_url="$1"
    local env_vars="$2"
    if [[ -z "$script_url" ]]; then
        echo "Script URL not provided, skipping."
        return
    fi
    # Write temp environment variables file, load and delete.
    TEMP_FILE=$(mktemp)
    IFS=' ' read -r -a vars <<< "$env_vars"
    for var in "${vars[@]}"; do
        echo "$var" >> "$TEMP_FILE"
    done
    # Source the temporary file and run the script
    set -a  # Automatically export all variables
    source "$TEMP_FILE"
    rm "$TEMP_FILE"
    set +a  # Stop automatically exporting variables

    wget "$script_url" -O external.sh
    chmod +x external.sh
    ./external.sh
    rm external.sh
}

proxy="test.proxy.internal:3128"
apt_packages="build-essential docker.io jq npm python3-dev python3-pip python-is-python3 \
shellcheck tar time unzip wget"
hwe_version="22.04"
github_runner_version=""
github_runner_arch="x64"
script_url="https://test-url.com/script.sh"
script_secrets="TEST_SECRET_ONE=HELLO TEST_SECRET_TWO=WORLD"

configure_proxy "$proxy"
install_apt_packages "$apt_packages" "$hwe_version"
disable_unattended_upgrades
enable_network_fair_queuing_congestion
configure_usr_local_bin
install_yarn
# install yq with ubuntu user due to GOPATH related go configuration settings
export -f install_yq
su ubuntu -c "bash -c 'install_yq'"
install_github_runner "$github_runner_version" "$github_runner_arch"
chown_home
configure_system_users
execute_script "$script_url" "$script_secrets"

# Make sure the disk is synced for snapshot
sync
echo "Finished sync"\
"""
    )
    # pylint: enable=R0801


def test__wait_for_cloud_init_complete_fail(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched _get_ssh_connection and connection.run functions that raises an\
        error.
    act: when _wait_for_cloud_init_complete is called.
    assert: CloudInitFailError is raised.
    """
    mock_connection = MagicMock()
    mock_connection.run.return_value = None
    monkeypatch.setattr(
        openstack_builder, "_get_ssh_connection", MagicMock(return_value=mock_connection)
    )

    with pytest.raises(errors.CloudInitFailError) as exc:
        openstack_builder._wait_for_cloud_init_complete(
            conn=mock_connection, server=MagicMock(), ssh_key=MagicMock()
        )

    assert "Invalid cloud-init status" in str(exc)


def test__wait_for_cloud_init_unexpected_exit(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched _get_ssh_connection and connection.run functions that raises an\
        error.
    act: when _wait_for_cloud_init_complete is called.
    assert: CloudInitFailError is raised.
    """
    mock_connection = MagicMock()
    mock_connection.get_server_console = (get_log_mock := MagicMock())
    mock_connection.run.side_effect = openstack_builder.invoke.exceptions.UnexpectedExit(
        result=MagicMock(), reason=MagicMock()
    )
    monkeypatch.setattr(
        openstack_builder, "_get_ssh_connection", MagicMock(return_value=mock_connection)
    )

    with pytest.raises(errors.CloudInitFailError):
        openstack_builder._wait_for_cloud_init_complete(
            conn=mock_connection, server=MagicMock(), ssh_key=MagicMock()
        )

    get_log_mock.assert_called_once()


def test__wait_for_cloud_init_complete(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched _get_ssh_connection and connection.run functions.
    act: when _wait_for_cloud_init_complete is called.
    assert: True is returned.
    """
    # patch tenacity retry to speed up testing
    openstack_builder._wait_for_cloud_init_complete.retry.wait = tenacity.wait_none()
    openstack_builder._wait_for_cloud_init_complete.retry.stop = tenacity.stop_after_attempt(1)
    mock_connection = MagicMock()
    result_mock = MagicMock()
    result_mock.stdout = "status: done"
    mock_connection.run.return_value = result_mock
    monkeypatch.setattr(
        openstack_builder, "_get_ssh_connection", MagicMock(return_value=mock_connection)
    )

    assert openstack_builder._wait_for_cloud_init_complete(
        conn=mock_connection, server=MagicMock(), ssh_key=MagicMock()
    )


def test__get_ssh_connection_no_networks():
    """
    arrange: given a mocked connection.get_server function that returns server with no addresses.
    act: when _get_ssh_connection is called.
    assert: AddressNotFoundError is raised.
    """
    # patch tenacity retry to speed up testing
    openstack_builder._get_ssh_connection.retry.wait = tenacity.wait_none()
    openstack_builder._get_ssh_connection.retry.stop = tenacity.stop_after_attempt(1)
    connection_mock = MagicMock()
    server_mock = MagicMock()
    server_mock.addresses = {}
    connection_mock.get_server = MagicMock(return_value=server_mock)

    with pytest.raises(errors.AddressNotFoundError) as exc:
        openstack_builder._get_ssh_connection(
            conn=connection_mock, server=MagicMock(), ssh_key=MagicMock()
        )

    assert "No addresses found for" in str(exc)


def test__get_ssh_connection_ssh_exception(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a mocked connection that raises SSHException on command execution.
    act: when _get_ssh_connection is called.
    assert: AddressNotFoundError is raised.
    """
    # patch tenacity retry to speed up testing
    openstack_builder._get_ssh_connection.retry.wait = tenacity.wait_none()
    openstack_builder._get_ssh_connection.retry.stop = tenacity.stop_after_attempt(1)
    connection_mock = MagicMock()
    server_mock = MagicMock()
    server_mock.addresses = {
        "test_addr_1": [{"addr": "test-address-1"}],
        "test_addr_2": [{"addr": "test-address-2"}],
    }
    connection_mock.get_server = MagicMock(return_value=server_mock)
    ssh_connection_mock = MagicMock()
    ssh_connection_mock.run.side_effect = paramiko.ssh_exception.SSHException
    monkeypatch.setattr(
        openstack_builder.fabric, "Connection", MagicMock(return_value=ssh_connection_mock)
    )

    with pytest.raises(errors.AddressNotFoundError) as exc:
        openstack_builder._get_ssh_connection(
            conn=connection_mock, server=MagicMock(), ssh_key=MagicMock()
        )

    assert "No connectable SSH addresses found" in str(exc)


def test__get_ssh_connection_ssh_invalid_result(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a mocked connection that returns invalid result.
    act: when _get_ssh_connection is called.
    assert: AddressNotFoundError is raised.
    """
    # patch tenacity retry to speed up testing
    openstack_builder._get_ssh_connection.retry.wait = tenacity.wait_none()
    openstack_builder._get_ssh_connection.retry.stop = tenacity.stop_after_attempt(1)
    connection_mock = MagicMock()
    server_mock = MagicMock()
    server_mock.addresses = {
        "test_addr_1": [{"addr": "test-address-1"}],
        "test_addr_2": [{"addr": "test-address-2"}],
    }
    connection_mock.get_server = MagicMock(return_value=server_mock)
    ssh_connection_mock = MagicMock()
    ssh_connection_mock.run.return_value = None
    monkeypatch.setattr(
        openstack_builder.fabric, "Connection", MagicMock(return_value=ssh_connection_mock)
    )

    with pytest.raises(errors.AddressNotFoundError) as exc:
        openstack_builder._get_ssh_connection(
            conn=connection_mock, server=MagicMock(), ssh_key=MagicMock()
        )

    assert "No connectable SSH addresses found" in str(exc)


def test__get_ssh_connection_ssh_invalid_stdout(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a mocked connection that returns invalid stdout.
    act: when _get_ssh_connection is called.
    assert: AddressNotFoundError is raised.
    """
    # patch tenacity retry to speed up testing
    openstack_builder._get_ssh_connection.retry.wait = tenacity.wait_none()
    openstack_builder._get_ssh_connection.retry.stop = tenacity.stop_after_attempt(1)
    connection_mock = MagicMock()
    server_mock = MagicMock()
    server_mock.addresses = {
        "test_addr_1": [{"addr": "test-address-1"}],
        "test_addr_2": [{"addr": "test-address-2"}],
    }
    connection_mock.get_server = MagicMock(return_value=server_mock)
    ssh_connection_mock = MagicMock()
    result_mock = MagicMock()
    result_mock.stdout = "invalid"
    ssh_connection_mock.run.return_value = result_mock
    monkeypatch.setattr(
        openstack_builder.fabric, "Connection", MagicMock(return_value=ssh_connection_mock)
    )

    with pytest.raises(errors.AddressNotFoundError) as exc:
        openstack_builder._get_ssh_connection(
            conn=connection_mock, server=MagicMock(), ssh_key=MagicMock()
        )

    assert "No connectable SSH addresses found" in str(exc)


def test__get_ssh_connection_ssh(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a mocked connection that returns valid stdout.
    act: when _get_ssh_connection is called.
    assert: expected connection is returned.
    """
    # patch tenacity retry to speed up testing
    openstack_builder._get_ssh_connection.retry.wait = tenacity.wait_none()
    openstack_builder._get_ssh_connection.retry.stop = tenacity.stop_after_attempt(1)
    connection_mock = MagicMock()
    server_mock = MagicMock()
    server_mock.addresses = {
        "test_addr_1": [{"addr": "test-address-1"}],
        "test_addr_2": [{"addr": "test-address-2"}],
    }
    connection_mock.get_server = MagicMock(return_value=server_mock)
    ssh_connection_mock = MagicMock()
    result_mock = MagicMock()
    result_mock.ok = True
    result_mock.stdout = "hello world"
    ssh_connection_mock.run.return_value = result_mock
    monkeypatch.setattr(
        openstack_builder.fabric, "Connection", MagicMock(return_value=ssh_connection_mock)
    )

    assert (
        openstack_builder._get_ssh_connection(
            conn=connection_mock, server=MagicMock(), ssh_key=MagicMock()
        )
        == ssh_connection_mock
    )


@pytest.mark.parametrize(
    "image_status",
    [
        pytest.param("queued", id="Queued status"),
        pytest.param("saving", id="Saving status"),
    ],
)
def test__wait_for_snapshot_complete_non_active(
    monkeypatch: pytest.MonkeyPatch, image_status: str
):
    """
    arrange: given a mocked get_image function that returns an image with parametrized status.
    act: when _wait_for_snapshot_complete is called.
    assert: TimeoutError is raised.
    """
    monkeypatch.setattr(openstack_builder.time, "sleep", MagicMock())
    connection_mock = MagicMock()
    image_mock = MagicMock()
    image_mock.status = image_status
    connection_mock.get_image.return_value = image_mock

    with pytest.raises(TimeoutError):
        openstack_builder._wait_for_snapshot_complete(conn=connection_mock, image=MagicMock())


@pytest.mark.parametrize(
    "num_not_active",
    [
        pytest.param(0, id="active right away"),
        pytest.param(10, id="active after 10 tries"),
    ],
)
def test__wait_for_snapshot_complete(monkeypatch: pytest.MonkeyPatch, num_not_active: int):
    """
    arrange: given a mocked get_image function that returns an image with active status.
    act: when _wait_for_snapshot_complete is called.
    assert: no errors are raised.
    """
    monkeypatch.setattr(openstack_builder.time, "sleep", MagicMock())
    connection_mock = MagicMock()
    not_active_mock = MagicMock()
    not_active_mock.status = "saving"
    image_mock = MagicMock()
    image_mock.status = "active"
    connection_mock.get_image.side_effect = [*[not_active_mock] * num_not_active, image_mock]

    assert (
        openstack_builder._wait_for_snapshot_complete(conn=connection_mock, image=MagicMock())
        is None
    )
