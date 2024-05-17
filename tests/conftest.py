# Copyright 2024 Canonical Ltd.
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
        "--openstack-clouds-yaml",
        action="store",
        help="The OpenStack clouds yaml contents the charm uses to connect to Openstack.",
    )
    parser.addoption(
        "--openstack-network-name",
        action="store",
        help="The Openstack network to create testing instances under.",
    )
    parser.addoption(
        "--openstack-flavor-name",
        action="store",
        help="The Openstack flavor to create testing instances with.",
    )
    # Private endpoint options
    parser.addoption(
        "--openstack-auth-url",
        action="store",
        help="The URL to Openstack authentication service, i.e. keystone.",
    )
    parser.addoption(
        "--openstack-password",
        action="store",
        help="The password to authenticate to Openstack service.",
    )
    parser.addoption(
        "--openstack-project-domain-name",
        action="store",
        help="The Openstack project domain name to use.",
    )
    parser.addoption(
        "--openstack-project-name",
        action="store",
        help="The Openstack project name to use.",
    )
    parser.addoption(
        "--openstack-user-domain-name",
        action="store",
        help="The Openstack user domain name to use.",
    )
    parser.addoption(
        "--openstack-user-name",
        action="store",
        help="The Openstack user to authenticate as.",
    )
    parser.addoption(
        "--openstack-region-name",
        action="store",
        help="The Openstack region to authenticate to.",
    )
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
