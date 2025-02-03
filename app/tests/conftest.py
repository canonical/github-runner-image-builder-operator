# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for github runner image builder app."""


from pytest import Parser


def pytest_addoption(parser: Parser):
    """Add options to pytest parser.

    Args:
        parser: The pytest argument parser.
    """
    parser.addoption("--image", action="store", help="The Ubuntu LTS base image to build.")
    parser.addoption(
        "--openstack-clouds-yaml",
        action="store",
        help="The OpenStack clouds yaml contents the charm uses to connect to Openstack.",
    )
    # Shared arguments
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
    parser.addoption(
        "--dockerhub-mirror",
        action="store",
        help="The dockerhub mirror URL to reduce API rate limiting.",
        default=None,
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
    # Private endpoint options ARM64
    parser.addoption(
        "--openstack-network-name-arm64",
        action="store",
        help="The Openstack network to create testing instances under.",
    )
    parser.addoption(
        "--openstack-flavor-name-arm64",
        action="store",
        help="The Openstack flavor to create testing instances with.",
    )
    parser.addoption(
        "--openstack-auth-url-arm64",
        action="store",
        help="The URL to Openstack authentication service, i.e. keystone.",
    )
    parser.addoption(
        "--openstack-project-domain-name-arm64",
        action="store",
        help="The Openstack project domain name to use.",
    )
    parser.addoption(
        "--openstack-project-name-arm64",
        action="store",
        help="The Openstack project name to use.",
    )
    parser.addoption(
        "--openstack-user-domain-name-arm64",
        action="store",
        help="The Openstack user domain name to use.",
    )
    parser.addoption(
        "--openstack-username-arm64",
        action="store",
        help="The Openstack user to authenticate as.",
    )
    parser.addoption(
        "--openstack-region-name-arm64",
        action="store",
        help="The Openstack region to authenticate to.",
    )
