"""Helpers for retrying requests to VWS."""

import contextlib
from collections.abc import Callable, Generator
from contextvars import ContextVar
from functools import wraps

from beartype import beartype
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import ConnectTimeout as RequestsConnectTimeout
from requests.exceptions import ReadTimeout as RequestsReadTimeout
from requests.exceptions import Timeout as RequestsTimeout
from tenacity import Retrying, retry
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed
from vws.exceptions.custom_exceptions import ServerError
from vws.exceptions.vws_exceptions import (
    TargetStatusProcessingError,
    TooManyRequestsError,
    UnknownTargetError,
)

# ``pytest-retry`` checks whether the type of the exception which failed a
# test is *in* this tuple, so a subclass of a listed type is not retried.
# ``requests`` raises the derived ``Timeout`` exceptions below, never
# ``Timeout``
# itself, so each one is listed. ``Timeout`` and ``ConnectionError`` stay
# for the ``tenacity`` retries, which do use ``isinstance``.
TRANSIENT_VWS_EXCEPTIONS = (
    TooManyRequestsError,
    ServerError,
    RequestsTimeout,
    RequestsReadTimeout,
    RequestsConnectTimeout,
    RequestsConnectionError,
)
TRANSIENT_VWS_RETRY_ATTEMPTS = 10

# Shared helpers send once unless an adapter supplies a retry policy.
# ContextVar requires a positional name at runtime.
_VWS_RETRYING: ContextVar[Retrying | None] = ContextVar(  # type: ignore[call-arg]
    "vws_retrying",
    default=None,
)


@contextlib.contextmanager
@beartype
def retrying_vws_requests(*, retrying: Retrying) -> Generator[None]:
    """Install an adapter's fixture retry policy for this scope.

    Yields:
        ``None``, with the policy active and its predecessor restored on exit.
    """
    token = _VWS_RETRYING.set(retrying)
    try:
        yield
    finally:
        _VWS_RETRYING.reset(token)


@beartype
def retry_transient_vws_failures[**P, T](
    operation: Callable[P, T],
) -> Callable[P, T]:
    """Apply the adapter's policy without multiplying nested retry budgets."""

    @wraps(wrapped=operation)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        """Run an operation under at most one transient retry loop."""
        retrying = _VWS_RETRYING.get()
        if retrying is None:
            return operation(*args, **kwargs)
        token = _VWS_RETRYING.set(None)
        try:
            return retrying.copy()(operation, *args, **kwargs)
        finally:
            _VWS_RETRYING.reset(token)

    return wrapped


# Real Vuforia sometimes reports a target which it has just created as
# unknown, because the target is not yet visible to the read path.
#
# This is deliberately kept out of ``TRANSIENT_VWS_EXCEPTIONS``. That tuple
# also decides which failures ``pytest-retry`` retries during tests, and an
# ``UnknownTargetError`` which a test did not expect is a result worth
# seeing rather than retrying away. Only code which has just been given a
# target's ID by Vuforia, and so knows the target exists, may use this.
RETRY_ON_TARGET_NOT_YET_VISIBLE = retry(
    retry=retry_if_exception_type(exception_types=UnknownTargetError),
    stop=stop_after_attempt(max_attempt_number=TRANSIENT_VWS_RETRY_ATTEMPTS),
    wait=wait_fixed(wait=2),
    reraise=True,
)


# Real Vuforia sometimes reports a target which has just been updated as
# still having its old status for a moment, so waiting for the target to be
# processed can return before the update has put the target back into
# processing. A request which then needs the target to be processed fails.
#
# Like ``RETRY_ON_TARGET_NOT_YET_VISIBLE``, this is kept out of
# ``TRANSIENT_VWS_EXCEPTIONS`` so that a test which does not expect a
# processing target sees the failure rather than retrying it away. Only code
# which has just waited for the target to be processed may use this.
RETRY_ON_TARGET_STILL_PROCESSING = retry(
    retry=retry_if_exception_type(exception_types=TargetStatusProcessingError),
    stop=stop_after_attempt(max_attempt_number=TRANSIENT_VWS_RETRY_ATTEMPTS),
    wait=wait_fixed(wait=2),
    reraise=True,
)
