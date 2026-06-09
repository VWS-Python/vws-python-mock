"""Helpers for retrying requests to VWS."""

from requests.exceptions import Timeout as RequestsTimeout
from tenacity import retry
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed
from vws.exceptions.custom_exceptions import ServerError
from vws.exceptions.vws_exceptions import (
    TooManyRequestsError,
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
