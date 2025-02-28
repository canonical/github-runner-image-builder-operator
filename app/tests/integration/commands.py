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
    """

    name: str
    command: str
    env: dict | None = None


TEST_RUNNER_COMMANDS = (
    Commands(name="simple hello world", command="echo hello world"),
    Commands(name="print groups", command="groups | grep sudo"),
    Commands(name="file permission to /usr/local/bin", command="ls -ld /usr/local/bin"),
    Commands(
        name="file permission to /usr/local/bin (create)", command="touch /usr/local/bin/test_file"
    ),
    Commands(
        name="check aproxy",
        command="sudo snap info aproxy && sudo snap services aproxy && sudo snap logs aproxy -n 100",
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
    Commands(
        name="test external script",
        command="cat /home/ubuntu/test.txt | grep 'hello world'",
    ),
    Commands(
        name="test external script secrets (should exist)",
        command='grep -q "SHOULD_EXIST" secret.txt',
    ),
    Commands(
        name="test external script secrets (should not exist)",
        command='! grep -q "SHOULD_NOT_EXIST" secret.txt',
    ),
)
