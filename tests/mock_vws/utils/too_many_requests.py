"""
Helpers for handling too many requests errors.
"""

from http import HTTPStatus

import requests
from vws.exceptions.custom_exceptions import ServerError
from vws.exceptions.response import Response
from vws.exceptions.vws_exceptions import TooManyRequests


def handle_server_errors(response: requests.Response) -> None:
    """
    Raise errors if the response is a 429 or 5xx.
    This is useful for retrying tests based on the exceptions they raise.

    Raises:
        vws.exceptions.vws_exceptions.TooManyRequests: The response is a 429.
        vws.exceptions.custom_exceptions.ServerError: The response is a 5xx.
    """
    vws_response = Response(
        text=response.text,
        url=response.url,
        status_code=response.status_code,
        headers=dict(response.headers),
        request_body=response.request.body,
    )
    # We do not cover this because in some test runs we will not hit the
    # error.
    if (
        response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    ):  # pragma: no cover
        # The Vuforia API returns a 429 response with no JSON body.
        # We raise this here to prompt a retry at a higher level.
        raise TooManyRequests(response=vws_response)

    # We do not cover this because in some test runs we will not hit the
    # error.
    if (
        response.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR
    ):  # pragma: no cover
        raise ServerError(response=vws_response)
