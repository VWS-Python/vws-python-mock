"""Helpers for handling too many requests errors."""

from http import HTTPStatus

from beartype import beartype
from vws.exceptions.custom_exceptions import ServerError
from vws.exceptions.vws_exceptions import TooManyRequestsError
from vws.response import Response


@beartype
def handle_server_errors(*, response: Response) -> None:
    """Raise errors if the response is a 429 or 5xx. This is useful for
    retrying tests based on the exceptions they raise.

    Raises:
        vws.exceptions.vws_exceptions.TooManyRequestsError: The response is a
            429.
        vws.exceptions.custom_exceptions.ServerError: The response is a 5xx.
    """
    # We do not cover this because in some test runs we will not hit the
    # error.
    if (
        response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    ):  # pragma: no cover
        # The Vuforia API returns a 429 response with no JSON body.
        # We raise this here to prompt a retry at a higher level.
        raise TooManyRequestsError(response=response)

    # We do not cover this because in some test runs we will not hit the
    # error.
    if (
        response.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR
    ):  # pragma: no cover
        raise ServerError(response=response)
