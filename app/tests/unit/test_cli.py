# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for cli module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

import itertools
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from github_runner_image_builder import cli, config
from github_runner_image_builder.cli import main


@pytest.fixture(scope="function", name="callback_path")
def callback_path_fixture(tmp_path: Path):
    """The testing callback file path."""
    test_path = tmp_path / "test"
    test_path.touch()
    return test_path


@pytest.fixture(scope="function", name="latest_build_id_inputs")
def latest_build_id_inputs_fixture():
    """Valid CLI run mode inputs."""
    return {"": "test-cloud-name", " ": "test-image-name"}


@pytest.fixture(scope="function", name="run_inputs")
def run_inputs_fixture(callback_path: Path):
    """Valid CLI run mode inputs."""
    return {
        "": "test-cloud-name",
        " ": "test-image-name",
        "--base-image": "noble",
        "--keep-revisions": "5",
        "--callback-script": str(callback_path),
        "--juju": "3.1/stable",
        "--dockerhub-cache": "https://dockerhub-cache.internal:5000",
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
    result = cli_runner.invoke(main, args=[invalid_action, "--help"])

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
    result = cli_runner.invoke(main, args=[action, "--help"])

    assert f"Usage: main {action}" in result.output


def test_initialize(monkeypatch: pytest.MonkeyPatch, cli_runner: CliRunner):
    """
    arrange: given a monkeypatched builder.initialize function.
    act: when cli init is invoked.
    assert: monkeypatched function is called.
    """
    monkeypatch.setattr(
        cli.openstack_builder, "initialize", (mock_openstack_init_func := MagicMock())
    )

    cli_runner.invoke(main, args=["init", "--cloud-name", "hello", "--arch", "x64"])

    mock_openstack_init_func.assert_called_with(
        arch=config.Arch.X64, cloud_name="hello", prefix=""
    )


@pytest.mark.parametrize(
    "invalid_args",
    [
        pytest.param({"": ""}, id="empty cloud name positional argument"),
        pytest.param({" ": ""}, id="empty image name positional argument"),
    ],
)
def test_invalid_latest_build_id_args(
    cli_runner: CliRunner, latest_build_id_inputs: dict, invalid_args: dict
):
    """
    arrange: given invalid latest-build-id action arguments.
    act: when _parse_args is called.
    assert: Error output is printed.
    """
    latest_build_id_inputs.update(invalid_args)
    inputs = list(
        # if flag does not exist, append it as a positional argument.
        value
        for value in itertools.chain.from_iterable(
            (flag, value) if flag.strip() else (value,)
            for (flag, value) in latest_build_id_inputs.items()
        )
        if value
    )

    result = cli_runner.invoke(main, args=["latest-build-id", *inputs])

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
        main, args=["latest-build-id", "test-cloud-name", "test-image-name"]
    )

    assert result.output == test_id


@pytest.mark.parametrize(
    "invalid_args",
    [
        pytest.param({"--base-image": ""}, id="no base-image"),
        pytest.param({"--base-image": "test"}, id="invalid base-image"),
        pytest.param(
            {"--callback-script": "non-existant-path"}, id="empty image name positional argument"
        ),
        pytest.param({"": ""}, id="empty cloud name positional argument"),
        pytest.param({" ": ""}, id="empty image name positional argument"),
        pytest.param({"--juju": "invalid-value"}, id="invalid juju channel value"),
        pytest.param({"--juju": "3.1/stable/edge"}, id="more than 1 / values"),
        pytest.param({"--dockerhub-cache": "invalidurl"}, id="invalid url"),
        pytest.param({"--dockerhub-cache": "no-scheme.internal:5000"}, id="no scheme"),
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

    result = cli_runner.invoke(main, args=["run", *inputs])

    assert (
        "Error: Invalid value for" in result.output or "Error: Missing argument" in result.output
    )


@pytest.mark.parametrize(
    "callback_script",
    [
        pytest.param(None, id="No callback script"),
        pytest.param(Path("tmp_path"), id="Callback script"),
    ],
)
def test_run(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner: CliRunner,
    tmp_path: Path,
    callback_script: Path | None,
):
    """
    arrange: given a monkeypatched builder.setup_builder function.
    act: when _build is called.
    assert: the mock function is called.
    """
    monkeypatch.setattr(cli.openstack_builder, "run", MagicMock())
    monkeypatch.setattr(cli.store, "upload_image", MagicMock())
    monkeypatch.setattr(cli.subprocess, "check_call", MagicMock())
    command = [
        "run",
        "--arch",
        "x64",
        "--base-image",
        "jammy",
        "test-cloud-name",
        "test-image-name",
    ]
    if callback_script:
        (callback_script_path := tmp_path / callback_script).touch(exist_ok=True)
        command.extend(["--callback-script", str(callback_script_path)])

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
