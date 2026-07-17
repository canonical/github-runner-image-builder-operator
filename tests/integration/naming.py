# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Shared naming for image-builder charm integration tests and orphan cleanup.

Producers (fixtures) and consumers (orphan cleanup) both import from here so
resource name formats cannot drift.
"""

import secrets
import string

# secrets.token_hex(4) → 8 hex characters
TEST_ID_LENGTH = 8
TEST_ID_ALPHABET = string.hexdigits.lower()

OPERATOR_APP_PREFIX = "image-builder-operator-"
CHARMHUB_APP_PREFIX = "image-builder-charmhub-"
TEST_CHARM_PREFIX = "test-"
TEST_CHARM_2_PREFIX = "test2-"
SSH_KEY_PREFIX = "test-image-builder-operator-keys-"
# Shared across concurrent charm-suite runs — orphan cleanup must not delete it.
SHARED_TEST_SECURITY_GROUP = "github-runner-image-builder-operator-test-security-group"

OPENSTACK_RESOURCE_PREFIXES: tuple[str, ...] = (
    OPERATOR_APP_PREFIX,
    CHARMHUB_APP_PREFIX,
    SSH_KEY_PREFIX,
    TEST_CHARM_2_PREFIX,  # longer than test-
    TEST_CHARM_PREFIX,
)


def generate_test_id() -> str:
    """Return a unique id for one suite run."""
    return secrets.token_hex(TEST_ID_LENGTH // 2)


def operator_app_name(test_id: str) -> str:
    """Return the image-builder-operator application name for *test_id*."""
    return f"{OPERATOR_APP_PREFIX}{test_id}"


def charmhub_app_name(test_id: str) -> str:
    """Return the image-builder charmhub application name for *test_id*."""
    return f"{CHARMHUB_APP_PREFIX}{test_id}"


def test_charm_app_name(test_id: str) -> str:
    """Return the primary test charm application name for *test_id*."""
    return f"{TEST_CHARM_PREFIX}{test_id}"


def test_charm_2_app_name(test_id: str) -> str:
    """Return the secondary test charm application name for *test_id*."""
    return f"{TEST_CHARM_2_PREFIX}{test_id}"


def ssh_key_name(test_id: str) -> str:
    """Return the OpenStack keypair name for *test_id*."""
    return f"{SSH_KEY_PREFIX}{test_id}"


def is_charm_openstack_resource_name(name: str | None) -> bool:
    """Return True if *name* belongs to this suite's OpenStack resources."""
    if not name:
        return False
    for prefix in OPENSTACK_RESOURCE_PREFIXES:
        if not name.startswith(prefix):
            continue
        rest = name[len(prefix) :]
        if not rest:
            continue
        test_id = rest.split("-", 1)[0]
        if len(test_id) == TEST_ID_LENGTH and all(c in TEST_ID_ALPHABET for c in test_id.lower()):
            return True
    return False
