# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for functions containing charm utilities."""

import functools
import logging
import typing

import ops

import state

logger = logging.getLogger(__name__)


class GithubRunnerImageBuilderCharmProtocol(typing.Protocol):  # pylint: disable=too-few-public-methods
    """Protocol to use for the decorator to block if invalid."""

    def update_status(self, status: ops.StatusBase) -> None:
        """Update the application and unit status.

        Args:
            status: the desired unit status.
        """


C = typing.TypeVar("C", bound=GithubRunnerImageBuilderCharmProtocol)
E = typing.TypeVar("E", bound=ops.EventBase)


def block_if_invalid_config(
    defer: bool = False,
) -> typing.Callable[[typing.Callable[[C, E], None]], typing.Callable[[C, E], None]]:
    """Create a decorator that puts the charm in blocked state if the config is wrong.

    Args:
        defer: whether to defer the event.

    Returns:
        the function decorator.
    """

    def decorator(
        method: typing.Callable[[C, E], None],
    ) -> typing.Callable[[C, E], None]:
        """Create a decorator that puts the charm in blocked state if the config is wrong.

        Args:
            method: observer method to wrap.

        Returns:
            the function wrapper.
        """

        @functools.wraps(method)
        def wrapper(instance: C, event: E) -> None:
            """Block the charm if the config is wrong.

            Args:
                instance: the instance of the class with the hook method.
                event: the event for the observer

            Returns:
                The value returned from the original function. That is, None.
            """
            try:
                return method(instance, event)
            except state.CharmConfigInvalidError as exc:
                if defer:
                    event.defer()
                logger.exception("Wrong Charm Configuration")
                instance.update_status(ops.BlockedStatus(exc.msg))
                return None

        return wrapper

    return decorator


def validate_aproxy_integration(
    method: typing.Callable[[C, E], None],
) -> typing.Callable[[C, E], None]:
    """Create a decorator that validates aproxy integration when proxy is configured.

    Blocks the charm if proxy data is set in the Juju model but aproxy is not integrated.

    Args:
        method: observer method to wrap.

    Returns:
        the function wrapper.
    """

    @functools.wraps(method)
    def wrapper(instance: C, event: E) -> None:
        """Validate aproxy integration and call the wrapped method.

        Args:
            instance: the instance of the class with the hook method.
            event: the event for the observer

        Returns:
            The value returned from the original function. That is, None.
        """
        proxy_data = state.ProxyConfig.from_env()
        aproxy_relation = instance.model.get_relation("juju-info")  # type: ignore
        if proxy_data and not aproxy_relation:
            logger.warning(
                "Proxy data configured in the juju model but aproxy charm is not integrated."
            )
            instance.update_status(
                ops.BlockedStatus(
                    "aproxy integration required when proxy is configured. "
                    "Please integrate with aproxy using: "
                    "juju integrate aproxy github-runner-image-builder"
                )
            )
            return None
        return method(instance, event)

    return wrapper
