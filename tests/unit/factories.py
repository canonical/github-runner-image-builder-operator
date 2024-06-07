# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Factories for generating test data."""

import secrets
import typing
from unittest.mock import MagicMock

import factory

from state import (
    BASE_IMAGE_CONFIG_NAME,
    BUILD_INTERVAL_CONFIG_NAME,
    OPENSTACK_AUTH_URL_CONFIG_NAME,
    OPENSTACK_PASSWORD_CONFIG_NAME,
    OPENSTACK_PROJECT_CONFIG_NAME,
    OPENSTACK_PROJECT_DOMAIN_CONFIG_NAME,
    OPENSTACK_USER_CONFIG_NAME,
    OPENSTACK_USER_DOMAIN_CONFIG_NAME,
    REVISION_HISTORY_LIMIT_CONFIG_NAME,
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


class MockCharmFactory(factory.Factory):
    """Mock GithubRunnerImageBuilder charm."""  # noqa: DCO060

    class Meta:  # pylint: disable=too-few-public-methods
        """Configuration for factory."""  # noqa: DCO060

        model = MagicMock

    app = MagicMock
    unit = MagicMock
    config = factory.Dict(
        {
            BASE_IMAGE_CONFIG_NAME: "jammy",
            BUILD_INTERVAL_CONFIG_NAME: "6",
            OPENSTACK_AUTH_URL_CONFIG_NAME: "http://testing-auth/keystone",
            OPENSTACK_PASSWORD_CONFIG_NAME: "testingvalue",
            OPENSTACK_PROJECT_DOMAIN_CONFIG_NAME: "project_domain_name",
            OPENSTACK_PROJECT_CONFIG_NAME: "project_name",
            OPENSTACK_USER_DOMAIN_CONFIG_NAME: "user_domain_name",
            OPENSTACK_USER_CONFIG_NAME: "username",
            REVISION_HISTORY_LIMIT_CONFIG_NAME: "5",
        }
    )


class CloudAuthFactory(factory.DictFactory):
    """Mock cloud auth dict object factory."""  # noqa: DCO060

    auth_url = factory.Faker("url")
    password = secrets.token_hex(16)
    project_domain_name = factory.Faker("name")
    project_name = factory.Faker("name")
    user_domain_name = factory.Faker("name")
    username = factory.Faker("name")


class CloudFactory(factory.DictFactory):
    """Mock cloud dict object factory."""  # noqa: DCO060

    clouds = {"testcloud": CloudAuthFactory()}
