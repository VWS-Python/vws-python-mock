"""Shared helpers for httpx2 mock tests."""

import asyncio
from collections.abc import Awaitable


def run[T](*, coroutine: Awaitable[T]) -> T:
    """Run a coroutine to completion.

    The test suite has no plugin for asynchronous tests, so asynchronous
    clients are driven from synchronous tests with this.

    Args:
        coroutine: The coroutine to run.

    Returns:
        The result of the given coroutine.
    """
    return asyncio.run(main=coroutine)
