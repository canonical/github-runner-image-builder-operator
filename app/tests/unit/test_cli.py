# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for cli module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

import itertools
import os
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from github_runner_image_builder import cli, config, logging
from github_runner_image_builder.cli import main

TEST_CLOUD_NAME = "testcloud"
REQUIRED_MAIN_INPUTS = [item for pair in {"--os-cloud": TEST_CLOUD_NAME}.items() for item in pair]


@pytest.fixture(name="monkeypatch_logging_configure", autouse=True)
def monkeypatch_logging_configure(monkeypatch):
    """Monkeypatch log dir to be accessible when testing."""
    monkeypatch.setattr(logging, "configure", MagicMock())


@pytest.fixture(name="monkeypatch_openstack_builder", autouse=True)
def monkeypatch_openstack_builder_fixture(monkeypatch):
    """Monkeypatch openstack_builder module."""
    monkeypatch.setattr(cli, "openstack_builder", (openstack_builder_mock := MagicMock()))
    openstack_builder_mock.determine_cloud = MagicMock(return_value=TEST_CLOUD_NAME)
    return openstack_builder_mock


@pytest.fixture(scope="function", name="run_inputs")
def run_inputs_fixture():
    """Valid CLI run mode inputs."""
    return {
        "": "test-image-name",
        "--base-image": "noble",
        "--keep-revisions": "5",
        "--script-url": "https://example.com",
    }


@pytest.fixture(scope="function", name="cli_runner")
def cli_runner_fixture():
    """The CliRunner fixture."""
    return CliRunner()


@pytest.mark.parametrize(
    "invalid_action",
    [
        pytest.param("testing", id="empty"),
        pytest.param("invalid", id="invalid"),
    ],
)
def test_main_invalid_action(cli_runner: CliRunner, invalid_action: str):
    """
    arrange: given invalid action arguments.
    act: when cli is invoked with invalid argument.
    assert: Error message is output.
    """
    result = cli_runner.invoke(main, args=[*REQUIRED_MAIN_INPUTS, invalid_action, "--help"])

    assert f"Error: No such command '{invalid_action}'" in result.output


@pytest.mark.parametrize(
    "action",
    [
        pytest.param("init", id="init"),
        pytest.param("latest-build-id", id="latest-build-id"),
        pytest.param("run", id="run"),
    ],
)
def test_main(cli_runner: CliRunner, action: str):
    """
    arrange: none.
    act: when main is called.
    assert: respective functions are called correctly.
    """
    result = cli_runner.invoke(main, args=[*REQUIRED_MAIN_INPUTS, action, "--help"])

    assert f"Usage: main {action}" in result.output


@pytest.mark.parametrize(
    "arch, expected_arch",
    [
        pytest.param("arm64", config.Arch.ARM64, id="arm64"),
        pytest.param("x64", config.Arch.X64, id="amd64"),
        pytest.param("s390x", config.Arch.S390X, id="s390x"),
        pytest.param("ppc64le", config.Arch.PPC64LE, id="ppc64le"),
    ],
)
def test_initialize(
    monkeypatch: pytest.MonkeyPatch, cli_runner: CliRunner, arch: str, expected_arch: str
):
    """
    arrange: given a monkeypatched builder.initialize function.
    act: when cli init is invoked.
    assert: monkeypatched function is called.
    """
    monkeypatch.setattr(
        cli.openstack_builder, "initialize", (mock_openstack_init_func := MagicMock())
    )

    cli_runner.invoke(main, args=[*REQUIRED_MAIN_INPUTS, "init", "--arch", arch])

    mock_openstack_init_func.assert_called_with(
        arch=expected_arch, cloud_name=TEST_CLOUD_NAME, prefix=""
    )


def test_initialize_invalid_args(cli_runner: CliRunner):
    """
    arrange: given invalid init action arguments.
    act: when _parse_args is called.
    assert: Error output is printed.
    """
    result = cli_runner.invoke(main, args=[*REQUIRED_MAIN_INPUTS, "init"])

    assert "Error: Missing option '--arch'" in result.output


def test_invalid_latest_build_id_args(cli_runner: CliRunner):
    """
    arrange: none.
    act: when latest-build-id is called with no image name.
    assert: Error output is printed.
    """
    result = cli_runner.invoke(main, args=[*REQUIRED_MAIN_INPUTS, "latest-build-id"])

    assert "Error: Missing argument " in result.output


def test_latest_build_id(monkeypatch: pytest.MonkeyPatch, cli_runner: CliRunner):
    """
    arrange: given valid latest-build-id args.
    act: when cli is invoked with latest-build-id.
    assert: latest-build-id is returned.
    """
    monkeypatch.setattr(
        cli.store, "get_latest_build_id", MagicMock(return_value=(test_id := "test-id"))
    )

    result = cli_runner.invoke(
        main, args=[*REQUIRED_MAIN_INPUTS, "latest-build-id", "test-image-name"]
    )

    assert result.output == test_id


@pytest.mark.parametrize(
    "invalid_args",
    [
        pytest.param({"--base-image": ""}, id="no base-image"),
        pytest.param({"--base-image": "test"}, id="invalid base-image"),
        pytest.param({"": ""}, id="empty image name positional argument"),
        pytest.param({"--script-url": "invalidurl"}, id="invalid url"),
        pytest.param({"--arch": "invalid"}, id="invalid arch"),
    ],
)
def test_invalid_run_args(cli_runner: CliRunner, run_inputs: dict, invalid_args: dict):
    """
    arrange: given invalid run action arguments.
    act: when _parse_args is called.
    assert: Error output is printed.
    """
    run_inputs.update(invalid_args)
    inputs = list(
        # if flag does not exist, append it as a positional argument.
        value
        for value in itertools.chain.from_iterable(
            (flag, value) if flag.strip() else (value,) for (flag, value) in run_inputs.items()
        )
        if value
    )

    result = cli_runner.invoke(main, args=[*REQUIRED_MAIN_INPUTS, "run", *inputs])

    assert (
        "Error: Invalid value for" in result.output or "Error: Missing argument" in result.output
    )


@pytest.mark.parametrize(
    "arch",
    [
        pytest.param("arm64", id="arm64"),
        pytest.param("x64", id="amd64"),
        pytest.param("s390x", id="s390x"),
    ],
)
def test_run(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner: CliRunner,
    arch: str,
):
    """
    arrange: given a monkeypatched builder.setup_builder function.
    act: when _build is called.
    assert: the mock function is called.
    """
    monkeypatch.setattr(cli.openstack_builder, "run", MagicMock())
    monkeypatch.setattr(cli.store, "upload_image", MagicMock())
    command = [
        *REQUIRED_MAIN_INPUTS,
        "run",
        "--arch",
        arch,
        "--base-image",
        "jammy",
        "test-image-name",
    ]

    result = cli_runner.invoke(
        main,
        command,
    )

    assert result.exit_code == 0


def test__load_secrets():
    """
    arrange: given secrets prefixed with IMAGE_BUILDER_SECRET_.
    act: when _load_secrets is called.
    assert: secrets are loaded correctly.
    """
    os.environ["IMAGE_BUILDER_SECRET_TEST_SECRET"] = (test_secret_value := "TEST_SECRET")
    os.environ["IMAGE_BUILDER_SECRET_TEST_SECRET_SECONDARY"] = test_secret_value

    assert cli._load_secrets() == {
        "TEST_SECRET": test_secret_value,
        "TEST_SECRET_SECONDARY": test_secret_value,
    }
