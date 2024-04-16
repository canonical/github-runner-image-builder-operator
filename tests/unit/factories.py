# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Factories for generating test data."""

import textwrap
from typing import Generic, TypeVar
from unittest.mock import MagicMock

import factory
from factory.faker import Faker

from state import (
    BASE_IMAGE_CONFIG_NAME,
    BUILD_INTERVAL_CONFIG_NAME,
    OPENSTACK_CLOUDS_YAML_CONFIG_NAME,
    REVISION_HISTORY_LIMIT_CONFIG_NAME,
)

T = TypeVar("T")


# DC060: Docstrings have been abbreviated for factories, checking for docstrings on model
# attributes can be skipped.


class BaseMetaFactory(Generic[T], factory.base.FactoryMetaClass):
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
            OPENSTACK_CLOUDS_YAML_CONFIG_NAME: textwrap.dedent(
                """
            clouds:
                sunbeam:
                    auth:
                    auth_url: http://10.20.21.12/openstack-keystone
                    password: PS2GoJZUnmtK
                    project_domain_name: users
                    project_name: demo
                    user_domain_name: users
                    username: demo
            """
            ).strip(),
            REVISION_HISTORY_LIMIT_CONFIG_NAME: "5",
        }
    )


class MockOpenstackImageFactory(factory.Factory):
    """Mock Openstack Image."""  # noqa: DCO060

    class Meta:  # pylint: disable=too-few-public-methods
        """Configuration for factory."""  # noqa: DCO060

        model = MagicMock

    id: str  # UUID
    created_at = Faker("date")  # Example format: 2024-04-16T04:31:12Z
