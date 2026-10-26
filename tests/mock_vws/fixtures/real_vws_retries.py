"""Bounded retry scheduling for real Vuforia fixture operations.

At most ten attempts are scheduled within 120 seconds of the first attempt.
A retry cannot interrupt an in-flight client request or its processing poll.
Valid Retry-After values are honored, even when that means giving up because
no retry fits the budget. Without one, full jitter spreads retries over an
exponentially increasing interval, starting at one second and capped at 30.
"""

import logging
from http import HTTPStatus

from beartype import beartype
from tenacity import RetryCallState, Retrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt, stop_before_delay
from tenacity.wait import wait_random_exponential
from urllib3.exceptions import InvalidHeader
from urllib3.util import Retry
from vws.exceptions.vws_exceptions import TooManyRequestsError

from tests.mock_vws.utils.retries import (
    TRANSIENT_VWS_EXCEPTIONS,
    TRANSIENT_VWS_RETRY_ATTEMPTS,
)

RETRY_BUDGET_SECONDS = 120
_LOGGER = logging.getLogger(name=__name__)
_FALLBACK_WAIT = wait_random_exponential(multiplier=1, max=30)
# Capped server delays must still exceed the budget to prevent early retries.
_RETRY_AFTER_PARSER = Retry(retry_after_max=RETRY_BUDGET_SECONDS + 1)


# Live-service throttling responses cannot be forced by the API tests.
@beartype
def wait_for_real_vws(
    retry_state: RetryCallState,
) -> float:  # pragma: no cover
    """Wait for the server's delay, otherwise use capped full jitter."""
    assert retry_state.outcome is not None
    error = retry_state.outcome.exception()
    if isinstance(error, TooManyRequestsError):
        for name, value in error.response.headers.items():
            if name.casefold() == "retry-after":
                try:
                    return float(
                        _RETRY_AFTER_PARSER.parse_retry_after(
                            retry_after=value
                        )
                    )
                except InvalidHeader:
                    break
                except ValueError, OverflowError:
                    # An unrepresentable delay must not cause an early retry.
                    return float(RETRY_BUDGET_SECONDS + 1)
    return _FALLBACK_WAIT(retry_state=retry_state)


@beartype
def _log_retry(retry_state: RetryCallState) -> None:  # pragma: no cover
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
