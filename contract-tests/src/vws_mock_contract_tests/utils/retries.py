"""Helpers for retrying requests to VWS."""

from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import ConnectTimeout as RequestsConnectTimeout
from requests.exceptions import ReadTimeout as RequestsReadTimeout
from requests.exceptions import Timeout as RequestsTimeout
from vws.exceptions.custom_exceptions import ServerError
from vws.exceptions.vws_exceptions import (
    TooManyRequestsError,
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
