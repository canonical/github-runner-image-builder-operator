# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utilities used by the app."""

import functools
import logging
import time
from typing import Callable, Optional, Type, TypeVar

from typing_extensions import ParamSpec

logger = logging.getLogger(__name__)


# Ignore pylint as this is a common name for types.
# Parameters of the function decorated with retry
ParamT = ParamSpec("ParamT")  # pylint: disable=invalid-name
# Return type of the function decorated with retry
ReturnT = TypeVar("ReturnT")  # pylint: disable=invalid-name


# This decorator has default arguments, one extra argument is not a problem.
def retry(  # pylint: disable=too-many-arguments, too-many-positional-arguments
    exception: Type[Exception] = Exception,
    tries: int = 1,
    delay: float = 0,
    max_delay: Optional[float] = None,
    backoff: float = 1,
    local_logger: logging.Logger = logger,
) -> Callable[[Callable[ParamT, ReturnT]], Callable[ParamT, ReturnT]]:
    """Parameterize the decorator for adding retry to functions.

    Args:
        exception: Exception type to be retried.
        tries: Number of attempts at retry.
        delay: Time in seconds to wait between retry.
        max_delay: Max time in seconds to wait between retry.
        backoff: Factor to increase the delay by each retry.
        local_logger: Logger for logging.

    Returns:
        The function decorator for retry.
    """

    def retry_decorator(
        func: Callable[ParamT, ReturnT],
    ) -> Callable[ParamT, ReturnT]:
        """Decorate function with retry.

        Args:
            func: The function to decorate.

        Returns:
            The resulting function with retry added.
        """

        @functools.wraps(func)
        def fn_with_retry(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ReturnT:
            """Wrap the function with retries.

            Args:
                args: The placeholder for decorated function's positional arguments.
                kwargs: The placeholder for decorated function's key word arguments.

            Raises:
                RuntimeError: Should be unreachable.

            Returns:
                Original return type of the decorated function.
            """
            remain_tries, current_delay = tries, delay

            for _ in range(tries):
                try:
                    return func(*args, **kwargs)
                # Error caught is set by the input of the function.
                except exception as err:  # pylint: disable=broad-exception-caught
                    remain_tries -= 1

                    if remain_tries == 0:
                        if local_logger is not None:
                            local_logger.exception("Retry limit of %s exceed: %s", tries, err)
                        raise

                    if local_logger is not None:
                        local_logger.warning(
                            "Retrying error in %s seconds: %s", current_delay, err
                        )
                        local_logger.debug("Error to be retried:", stack_info=True)

                    time.sleep(current_delay)

                    current_delay *= backoff

                    if max_delay is not None:
                        current_delay = min(current_delay, max_delay)

            raise RuntimeError("Unreachable code of retry logic.")  # pragma: nocover

        return fn_with_retry

    return retry_decorator
