"""
Helpers for handling too many requests errors.
"""

from http import HTTPStatus

import requests
from vws.exceptions.response import Response
from vws.exceptions.vws_exceptions import TooManyRequests


def handle_too_many_requests(response: requests.Response) -> None:
    """
    Raise a :class:`vws.exceptions.vws_exceptions.TooManyRequests` if the
    response is a 429.

    Raises:
        vws.exceptions.vws_exceptions.TooManyRequests: The response is a 429.
    """
    # We do not cover this because in some test runs we will not hit the
    # error.
    if (
        response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    ):  # pragma: no cover
        # The Vuforia API returns a 429 response with no JSON body.
        # We raise this here to prompt a retry at a higher level.
        vws_response = Response(
            text=response.text,
            url=response.url,
            status_code=response.status_code,
            headers=dict(response.headers),
            request_body=response.request.body,
        )
        raise TooManyRequests(response=vws_response)
