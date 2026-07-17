# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Shared naming for image-builder app integration tests and orphan cleanup.

Producers (fixtures) and consumers (orphan cleanup) both import from here so
resource name formats cannot drift.
"""

import secrets
import string

# Two lowercase letters per historical app suite test_id fixture.
TEST_ID_LENGTH = 2
TEST_ID_ALPHABET = string.ascii_lowercase

SSH_KEY_PREFIX = "test-image-builder-keys-"
TEST_SERVER_PREFIX = "test-image-builder-run-"
SECURITY_GROUP_PREFIX = "github-runner-image-builder-test-security-group-"
# Runtime permanent group — never delete.
SHARED_SECURITY_GROUP = "github-runner-image-builder-v1"


def generate_test_id() -> str:
    """Return a unique id for one suite run."""
    return "".join(secrets.choice(TEST_ID_ALPHABET) for _ in range(TEST_ID_LENGTH))


def ssh_key_name(test_id: str) -> str:
    """Return the OpenStack keypair name for *test_id*."""
    return f"{SSH_KEY_PREFIX}{test_id}"


def test_server_name(test_id: str) -> str:
    """Return the validation server name for *test_id*."""
    return f"{TEST_SERVER_PREFIX}{test_id}"


def security_group_name(test_id: str) -> str:
    """Return the suite-scoped OpenStack security group name for *test_id*."""
    return f"{SECURITY_GROUP_PREFIX}{test_id}"


def built_resource_prefix(test_id: str) -> str:
    """Return the prefix used by the app for built images and builder artifacts."""
    return f"{test_id}-image-builder-"


def is_app_openstack_resource_name(name: str | None) -> bool:
    """Return True if *name* belongs to this suite's OpenStack resources."""
    if not name or name == SHARED_SECURITY_GROUP:
        return False
    # Suite-scoped fixture resources.
    for prefix in (SSH_KEY_PREFIX, TEST_SERVER_PREFIX, SECURITY_GROUP_PREFIX):
        if name.startswith(prefix):
            rest = name[len(prefix) :]
            if len(rest) >= TEST_ID_LENGTH and all(
                c in TEST_ID_ALPHABET for c in rest[:TEST_ID_LENGTH]
            ):
                return True
    # App builder output: {test_id}-image-builder-...
    if len(name) > TEST_ID_LENGTH + len("-image-builder-"):
        candidate = name[:TEST_ID_LENGTH]
        if all(c in TEST_ID_ALPHABET for c in candidate) and name[TEST_ID_LENGTH:].startswith(
            "-image-builder-"
        ):
            return True
    return False


def is_app_test_security_group_name(name: str | None) -> bool:
    """Return True if *name* is a suite-scoped test security group."""
    if not name or not name.startswith(SECURITY_GROUP_PREFIX):
        return False
    rest = name[len(SECURITY_GROUP_PREFIX) :]
    return len(rest) >= TEST_ID_LENGTH and all(c in TEST_ID_ALPHABET for c in rest[:TEST_ID_LENGTH])
