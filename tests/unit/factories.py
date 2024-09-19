# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Factories for generating test data."""

import typing
from unittest.mock import MagicMock

import factory

from state import (
    APP_CHANNEL_CONFIG_NAME,
    BASE_IMAGE_CONFIG_NAME,
    BUILD_INTERVAL_CONFIG_NAME,
    OPENSTACK_AUTH_URL_CONFIG_NAME,
    OPENSTACK_PASSWORD_CONFIG_NAME,
    OPENSTACK_PROJECT_CONFIG_NAME,
    OPENSTACK_PROJECT_DOMAIN_CONFIG_NAME,
    OPENSTACK_USER_CONFIG_NAME,
    OPENSTACK_USER_DOMAIN_CONFIG_NAME,
    REVISION_HISTORY_LIMIT_CONFIG_NAME,
    RUNNER_VERSION_CONFIG_NAME,
)

T = typing.TypeVar("T")


# DC060: Docstrings have been abbreviated for factories, checking for docstrings on model
# attributes can be skipped.


class BaseMetaFactory(typing.Generic[T], factory.base.FactoryMetaClass):
    """Used for type hints of factories."""

    # No need for docstring because it is used for type hints
    def __call__(cls, *args, **kwargs) -> T:  # noqa: N805
        """Used for type hints of factories."""  # noqa: DCO020
        return super().__call__(*args, **kwargs)  # noqa: DCO030


class MockUnitFactory(factory.Factory):
    """Mock GitHubRunnerImageBuilder charm unit."""  # noqa: DCO060

    class Meta:  # pylint: disable=too-few-public-methods
        """Configuration for factory."""  # noqa: DCO060

        model = MagicMock

    name: str


class MockCharmFactory(factory.Factory):
    """Mock GithubRunnerImageBuilder charm."""  # noqa: DCO060

    class Meta:  # pylint: disable=too-few-public-methods
        """Configuration for factory."""  # noqa: DCO060

        model = MagicMock

    app = MagicMock
    unit = MockUnitFactory()
    config = factory.Dict(
        {
            APP_CHANNEL_CONFIG_NAME: "edge",
            BASE_IMAGE_CONFIG_NAME: "jammy",
            BUILD_INTERVAL_CONFIG_NAME: "6",
            OPENSTACK_AUTH_URL_CONFIG_NAME: "http://testing-auth/keystone",
            OPENSTACK_PASSWORD_CONFIG_NAME: "testingvalue",
            OPENSTACK_PROJECT_DOMAIN_CONFIG_NAME: "project_domain_name",
            OPENSTACK_PROJECT_CONFIG_NAME: "project_name",
            OPENSTACK_USER_DOMAIN_CONFIG_NAME: "user_domain_name",
            OPENSTACK_USER_CONFIG_NAME: "username",
            REVISION_HISTORY_LIMIT_CONFIG_NAME: "5",
            RUNNER_VERSION_CONFIG_NAME: "1.234.5",
        }
    )


class CloudAuthFactory(factory.DictFactory):
    """Mock cloud auth dict object factory."""  # noqa: DCO060

    auth_url = "test-auth-url"
    # We need to use known password for unit testing
    password = "test-password"  # nosec: B105:hardcoded_password_string
    project_domain_name = "test-project-domain"
    project_name = "test-project-name"
    user_domain_name = "test-user-domain"
    username = "test-username"


class CloudFactory(factory.Factory):
    """Mock cloud dict object factory."""  # noqa: DCO060

    class Meta:  # pylint: disable=too-few-public-methods
        """Configuration for factory."""  # noqa: DCO060

        model = MagicMock

    clouds = {"testcloud": CloudAuthFactory()}
