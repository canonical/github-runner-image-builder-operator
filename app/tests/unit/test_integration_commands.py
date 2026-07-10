# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for arch-conditional integration test command selection."""

from github_runner_image_builder.config import Arch
from tests.integration import commands


def test_commands_for_arch_includes_arm_commands_for_arm():
    """
    arrange: given the ARM architecture.
    act: when commands_for_arch is called.
    assert: the returned commands include every ARM_RUNNER_COMMANDS entry and all base commands.
    """
    result = commands.commands_for_arch(Arch.ARM)

    for arm_command in commands.ARM_RUNNER_COMMANDS:
        assert arm_command in result
    for base_command in commands.TEST_RUNNER_COMMANDS:
        assert base_command in result


def test_commands_for_arch_excludes_arm_commands_for_non_arm():
    """
    arrange: given a non-ARM architecture.
    act: when commands_for_arch is called.
    assert: the returned commands are exactly the base commands (no ARM_RUNNER_COMMANDS).
    """
    result = commands.commands_for_arch(Arch.X64)

    assert tuple(result) == tuple(commands.TEST_RUNNER_COMMANDS)
    for arm_command in commands.ARM_RUNNER_COMMANDS:
        assert arm_command not in result
