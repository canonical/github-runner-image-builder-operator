# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for defining unit test fixtures."""

import secrets
from unittest.mock import MagicMock

import pytest
import tenacity
from ops.testing import Harness

import builder
import image
import state
from charm import GithubRunnerImageBuilderCharm

# Need access to protected functions for testing
# pylint:disable=protected-access


@pytest.fixture(name="harness")
def harness_fixture():
    """The ops testing harness fixture."""
    harness = Harness(GithubRunnerImageBuilderCharm)
    harness.begin()

    # Replace config_changed handler temporarily.
    config_changed_handler = harness.charm._on_config_changed
    harness.charm._on_config_changed = MagicMock()
    harness.update_config(
        {
            state.EXTERNAL_BUILD_CONFIG_NAME: True,
            state.OPENSTACK_AUTH_URL_CONFIG_NAME: "https://test-auth-url.com/",
            state.OPENSTACK_PASSWORD_CONFIG_NAME: secrets.token_hex(16),
            state.OPENSTACK_PROJECT_DOMAIN_CONFIG_NAME: "test",
            state.OPENSTACK_PROJECT_CONFIG_NAME: "test",
            state.OPENSTACK_USER_DOMAIN_CONFIG_NAME: "test",
            state.OPENSTACK_USER_CONFIG_NAME: "test",
        }
    )
    harness.charm._on_config_changed = config_changed_handler

    yield harness

    harness.cleanup()


@pytest.fixture(name="charm")
def charm_fixture(harness: Harness) -> GithubRunnerImageBuilderCharm:
    """The charm fixture from harness."""
    return harness.charm


@pytest.fixture(name="image_observer")
def image_observer_fixture(charm: GithubRunnerImageBuilderCharm) -> image.Observer:
    """The image observer from harness."""
    return charm.image_observer


@pytest.fixture(name="patch_tenacity_wait", autouse=True)
def patch_tenacity_wait_fixture():
    """Patch tenacity wait function to speed up testing."""
    builder._run.retry.wait = tenacity.wait_fixed(0)
