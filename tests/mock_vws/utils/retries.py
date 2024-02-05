"""Helpers for retrying requests to VWS."""

from tenacity import retry
from tenacity.retry import retry_if_exception_type
from tenacity.wait import wait_fixed
from vws.exceptions.custom_exceptions import ServerError
from vws.exceptions.vws_exceptions import (
    TooManyRequests,
)

RETRY_EXCEPTIONS = (TooManyRequests, ServerError)

# We rely on pytest-retry for exceptions *during* tests.
# We use tenacity for exceptions *before* tests.
# See https://github.com/str0zzapreti/pytest-retry/issues/33.
RETRY_ON_TOO_MANY_REQUESTS = retry(
    retry=retry_if_exception_type(exception_types=RETRY_EXCEPTIONS),
    wait=wait_fixed(wait=10),
    reraise=True,
)
