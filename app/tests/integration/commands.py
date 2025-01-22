# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test command constants."""

import dataclasses


@dataclasses.dataclass
class Commands:
    """Test commands to execute.

    Attributes:
        name: The test name.
        command: The command to execute.
        env: Additional run envs.
        external: OpenStack VM test only (Chroot unsupported test).
    """

    name: str
    command: str
    env: dict | None = None
    external: bool = False


# This is matched with E2E test run of github-runner-operator charm.
TEST_RUNNER_COMMANDS = (
    Commands(name="simple hello world", command="echo hello world"),
    Commands(name="print groups", command="groups | grep sudo"),
    Commands(name="file permission to /usr/local/bin", command="ls -ld /usr/local/bin"),
    Commands(
        name="file permission to /usr/local/bin (create)", command="touch /usr/local/bin/test_file"
    ),
    Commands(name="install microk8s", command="sudo snap install microk8s --classic"),
    # This is a special helper command to configure dockerhub registry if available.
    Commands(
        name="configure dockerhub mirror",
        command="""echo 'server = "{registry_url}"

[host.{hostname}:{port}]
capabilities = ["pull", "resolve"]
' | sudo tee /var/snap/microk8s/current/args/certs.d/docker.io/hosts.toml && \
sudo microk8s stop && sudo microk8s start""",
    ),
    Commands(name="wait for microk8s", command="microk8s status --wait-ready"),
    Commands(
        name="deploy nginx in microk8s",
        command="microk8s kubectl create deployment nginx --image=nginx",
    ),
    Commands(
        name="wait for nginx",
        command="microk8s kubectl rollout status deployment/nginx --timeout=20m",
    ),
    Commands(name="update apt in docker", command="docker run python:3.10-slim apt-get update"),
    Commands(name="docker version", command="docker version"),
    Commands(name="check python3 alias", command="python --version"),
    Commands(name="pip version", command="python3 -m pip --version"),
    Commands(name="npm version", command="npm --version"),
    Commands(name="shellcheck version", command="shellcheck --version"),
    Commands(name="jq version", command="jq --version"),
    Commands(name="yq version", command="yq --version"),
    Commands(name="apt update", command="sudo apt-get update -y"),
    Commands(name="install pipx", command="sudo apt-get install -y pipx"),
    Commands(name="pipx add path", command="pipx ensurepath"),
    Commands(name="install check-jsonschema", command="pipx install check-jsonschema"),
    Commands(
        name="check jsonschema",
        command="check-jsonschema --version",
        # pipx has been added to PATH but still requires additional PATH env since
        # default shell is not bash in OpenStack
        env={"PATH": "$PATH:/home/ubuntu/.local/bin"},
    ),
    Commands(name="unzip version", command="unzip -v"),
    Commands(name="gh version", command="gh --version"),
    Commands(
        name="test sctp support", command="sudo apt-get install lksctp-tools -yq && checksctp"
    ),
    Commands(name="test HWE kernel", command="uname -a | grep generic"),
    Commands(
        name="test network congestion policy(fq)",
        command="sudo sysctl -a | grep 'net.core.default_qdisc = fq'",
    ),
    Commands(
        name="test network congestion policy",
        command="sudo sysctl -a | grep 'net.ipv4.tcp_congestion_control = bbr'",
    ),
    Commands(name="test juju installed", command="juju version | grep 3.1", external=True),
    Commands(
        name="test external script",
        command="cat /home/ubuntu/test.txt | grep 'hello world'",
        external=True,
    ),
    Commands(
        name="test external script secrets (should exist)",
        command='grep -q "SHOULD_EXIST" secret.txt',
        external=True,
    ),
    Commands(
        name="test external script secrets (should not exist)",
        command='! grep -q "SHOULD_NOT_EXIST" secret.txt',
        external=True,
    ),
)
