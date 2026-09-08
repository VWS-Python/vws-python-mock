"""Helpers for retrying requests to VWS."""

from requests.exceptions import Timeout as RequestsTimeout
from tenacity import retry
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed
from vws.exceptions.custom_exceptions import ServerError
from vws.exceptions.vws_exceptions import (
    TargetStatusProcessingError,
    TooManyRequestsError,
    UnknownTargetError,
)

TRANSIENT_VWS_EXCEPTIONS = (TooManyRequestsError, ServerError, RequestsTimeout)
TRANSIENT_VWS_RETRY_ATTEMPTS = 10

# We rely on pytest-retry for exceptions *during* tests.
# We use tenacity for exceptions *before* tests.
# See https://github.com/str0zzapreti/pytest-retry/issues/33.
RETRY_ON_TRANSIENT_VWS_FAILURE = retry(
    retry=retry_if_exception_type(exception_types=TRANSIENT_VWS_EXCEPTIONS),
    stop=stop_after_attempt(max_attempt_number=TRANSIENT_VWS_RETRY_ATTEMPTS),
    wait=wait_fixed(wait=10),
    reraise=True,
)


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
