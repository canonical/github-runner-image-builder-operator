#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration testing module."""

import logging

from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)


async def test_build_and_deploy(ops_test: OpsTest):
    """Do nothing."""
    pass
