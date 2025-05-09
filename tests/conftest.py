# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github runner charm."""


from pytest import Parser


def pytest_addoption(parser: Parser):
    """Add options to pytest parser.

    Args:
        parser: The pytest argument parser.
    """
    parser.addoption(
        "--charm-file",
        action="append",
        help="The prebuilt github-runner-image-builder-operator charm file.",
    )
    parser.addoption(
        "--arch",
        action="store",
        help="The architecture to build for.",
        choices=["amd64", "arm64", "s390x"],
        default="amd64",
    )
    # Private endpoint options AMD64
    parser.addoption(
        "--openstack-network-name-amd64",
        action="store",
        help="The Openstack network to create testing instances under.",
    )
    parser.addoption(
        "--openstack-flavor-name-amd64",
        action="store",
        help="The Openstack flavor to create testing instances with.",
    )
    parser.addoption(
        "--openstack-auth-url-amd64",
        action="store",
        help="The URL to Openstack authentication service, i.e. keystone.",
    )
    parser.addoption(
        "--openstack-project-domain-name-amd64",
        action="store",
        help="The Openstack project domain name to use.",
    )
    parser.addoption(
        "--openstack-project-name-amd64",
        action="store",
        help="The Openstack project name to use.",
    )
    parser.addoption(
        "--openstack-user-domain-name-amd64",
        action="store",
        help="The Openstack user domain name to use.",
    )
    parser.addoption(
        "--openstack-username-amd64",
        action="store",
        help="The Openstack user to authenticate as.",
    )
    parser.addoption(
        "--openstack-region-name-amd64",
        action="store",
        help="The Openstack region to authenticate to.",
    )
    # Shared private endpoint options
    parser.addoption(
        "--proxy",
        action="store",
        help="The HTTP proxy URL to apply on the Openstack runners.",
        default=None,
    )
    parser.addoption(
        "--no-proxy",
        action="store",
        help="The no proxy URL(s) to apply on the Openstack runners.",
        default=None,
    )
