# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for utils module."""

import logging
from unittest.mock import MagicMock

import pytest

from github_runner_image_builder.utils import retry


def test_retry_with_logger():
    """
    arrange: given a function that raises exception decorated with retry.
    act: when the function is called.
    assert: the function is retried and raises eventually.
    """
    counter = MagicMock()
    num_tries = 2
    logger = logging.getLogger("test")

    with pytest.raises(ValueError):

        @retry(
            exception=ValueError,
            tries=num_tries,
            delay=0,
            max_delay=0,
            backoff=1,
            local_logger=logger,
        )
        def decorated_func():
            """A test function that is being decorated.

            Raises:
                ValueError: always.
            """
            counter()
            raise ValueError

        decorated_func()

    assert counter.call_count == num_tries


def test_retry_no_logger():
    """
    arrange: given a function that raises exception decorated with retry.
    act: when the function is called.
    assert: the function is retried and raises eventually.
    """
    counter = MagicMock()
    num_tries = 2

    with pytest.raises(ValueError):

        @retry(
            exception=ValueError,
            tries=num_tries,
            delay=0,
            max_delay=None,
            backoff=1,
            local_logger=None,
        )
        def decorated_func():
            """A test function that is being decorated.

            Raises:
                ValueError: always.
            """
            counter()
            raise ValueError

        decorated_func()

    assert counter.call_count == num_tries
