# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Factories for generating test data."""

from typing import Generic, TypeVar
from unittest.mock import MagicMock

import factory
from factory.faker import Faker

T = TypeVar("T")


# DC060: Docstrings have been abbreviated for factories, checking for docstrings on model
# attributes can be skipped.


class BaseMetaFactory(Generic[T], factory.base.FactoryMetaClass):
    """Used for type hints of factories."""

    # No need for docstring because it is used for type hints
    def __call__(cls, *args, **kwargs) -> T:  # noqa: N805
        """Used for type hints of factories."""  # noqa: DCO020
        return super().__call__(*args, **kwargs)  # noqa: DCO030


class MockOpenstackImageFactory(factory.Factory):
    """Mock Openstack Image."""  # noqa: DCO060

    class Meta:  # pylint: disable=too-few-public-methods
        """Configuration for factory."""  # noqa: DCO060

        model = MagicMock

    id: str  # UUID
    created_at = Faker("date")  # Example format: 2024-04-16T04:31:12Z


class MockRequestsReponseFactory(factory.Factory):
    """Mock requests response."""  # noqa: DCO060

    class Meta:  # pylint: disable=too-few-public-methods
        """Configuration for factory."""  # noqa: DCO060

        model = MagicMock

    is_redirect: bool
