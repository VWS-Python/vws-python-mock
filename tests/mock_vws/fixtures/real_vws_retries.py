"""Bounded retry scheduling for real Vuforia fixture operations.

At most ten attempts are scheduled within 120 seconds of the first attempt.
A retry cannot interrupt an in-flight client request or its processing poll.
Valid Retry-After values are honored, even when that means giving up because
no retry fits the budget. Without one, full jitter spreads retries over an
exponentially increasing interval, starting at one second and capped at 30.
"""

import datetime
import logging
from email.utils import parsedate_to_datetime
from http import HTTPStatus

from beartype import beartype
from tenacity import RetryCallState, Retrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt, stop_before_delay
from tenacity.wait import wait_random_exponential
from vws.exceptions.vws_exceptions import TooManyRequestsError

from tests.mock_vws.utils.retries import (
    TRANSIENT_VWS_EXCEPTIONS,
    TRANSIENT_VWS_RETRY_ATTEMPTS,
)

RETRY_BUDGET_SECONDS = 120
_LOGGER = logging.getLogger(name=__name__)
_MAX_DELAY_DIGITS = 9
_FALLBACK_WAIT = wait_random_exponential(multiplier=1, max=30)


@beartype
def _retry_after_seconds(
    *, value: str, now: datetime.datetime
) -> float | None:
    """Read HTTP delay-seconds or an HTTP-date, rejecting malformed values."""
    value = value.strip()
    if value.isascii() and value.isdecimal():
        value = value.lstrip("0") or "0"
        # Longer values exceed any useful retry deadline. Avoid integer
        # conversion limits and float overflow for external header values.
        if len(value) > _MAX_DELAY_DIGITS:
            return float("inf")
        return float(value)
    try:
        retry_at = parsedate_to_datetime(data=value)
    except ValueError, TypeError, OverflowError:
        return None
    if retry_at.tzinfo is None:
        return None
    return max(0.0, (retry_at - now).total_seconds())


@beartype
def wait_for_real_vws(retry_state: RetryCallState) -> float:
    """Wait for the server's delay, otherwise use capped full jitter."""
    assert retry_state.outcome is not None
    error = retry_state.outcome.exception()
    if isinstance(error, TooManyRequestsError):
        for name, value in error.response.headers.items():
            if name.casefold() == "retry-after":
                delay = _retry_after_seconds(
                    value=value,
                    now=datetime.datetime.now(tz=datetime.UTC),
                )
                if delay is not None:
                    return delay
    return _FALLBACK_WAIT(retry_state=retry_state)


@beartype
def _log_retry(retry_state: RetryCallState) -> None:
    """Log timing and error type without request headers or
    credentials.
    """
    assert retry_state.outcome is not None
    assert retry_state.next_action is not None
    error = retry_state.outcome.exception()
    status = (
        HTTPStatus.TOO_MANY_REQUESTS
        if isinstance(error, TooManyRequestsError)
        else None
    )
    _LOGGER.warning(
        "Retrying real Vuforia operation after attempt %d: "
        "%s (status %s), delay %.3fs",
        retry_state.attempt_number,
        type(error).__name__,
        status,
        retry_state.next_action.sleep,
    )


REAL_VWS_RETRYING = Retrying(
    retry=retry_if_exception_type(exception_types=TRANSIENT_VWS_EXCEPTIONS),
    stop=(
        stop_after_attempt(max_attempt_number=TRANSIENT_VWS_RETRY_ATTEMPTS)
        | stop_before_delay(max_delay=RETRY_BUDGET_SECONDS)
    ),
    wait=wait_for_real_vws,
    before_sleep=_log_retry,
    reraise=True,
)
