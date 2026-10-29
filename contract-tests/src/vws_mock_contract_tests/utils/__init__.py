"""Utilities for tests."""

from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from beartype import beartype
from requests.structures import CaseInsensitiveDict
from vws.response import Response

from vws_mock_contract_tests.utils.model_target_retries import (
    send_with_transient_retries,
)
from vws_mock_contract_tests.utils.request_timeout_policy import (
    propagating_request_timeouts,
)

_REQUEST_TIMEOUT_SECONDS = 5


@beartype
def _send_request(
    *,
    method: str,
    url: str,
    headers: Mapping[str, str],
    data: bytes | str,
) -> Response:
    """Send a request with exactly the given headers."""
    request = requests.Request(
        method=method,
        url=url,
        headers=headers,
        data=data,
    )
    prepared_request = request.prepare()
    prepared_request.headers = CaseInsensitiveDict(data=headers)
    session = requests.Session()
    with propagating_request_timeouts(url=url):
        requests_response = session.send(
            request=prepared_request,
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
    return Response(
        text=requests_response.text,
        url=requests_response.url,
        status_code=requests_response.status_code,
        headers=dict(requests_response.headers),
        request_body=requests_response.request.body,
        tell_position=requests_response.raw.tell(),
        content=requests_response.content,
    )


@dataclass(frozen=True, kw_only=True)
class Endpoint:
    """Details of endpoints to be called in tests.

    Args:
        prepared_request: A request to make which would be successful.
        successful_headers_result_code: The expected result code if the
            example path is requested with the method.
        successful_headers_status_code: The expected status code if the
            example path is requested with the method.
        access_key: The access key used in the prepared request.
        secret_key: The secret key used in the prepared request.
        path_url: The path of the endpoint.
        base_url: The base URL of the endpoint.

    Attributes:
        prepared_request: A request to make which would be successful.
        successful_headers_result_code: The expected result code if the
            example path is requested with the method.
        successful_headers_status_code: The expected status code if the
            example path is requested with the method.
        access_key: The access key used in the prepared request.
        secret_key: The secret key used in the prepared request.
        path_url: The path of the endpoint.
        base_url: The base URL of the endpoint.
    """

    base_url: str
    path_url: str
    method: str
    headers: Mapping[str, str]
    data: bytes | str
    successful_headers_result_code: str | None
    successful_headers_status_code: int
    access_key: str
    secret_key: str

    @beartype
    def send(self) -> Response:
        """Send the request."""
        return _send_request(
            method=self.method,
            url=urljoin(base=self.base_url, url=self.path_url),
            headers=self.headers,
            data=self.data,
        )

    @property
    def auth_header_content_type(self) -> str:
        """The content type to use for the `Authorization` header."""
        full_content_type = dict(self.headers).get("Content-Type", "")
        return full_content_type.split(sep=";")[0]


@dataclass(frozen=True, kw_only=True)
class ModelTargetEndpoint:
    """Details of Model Target Web API endpoints to be called in tests.

    Args:
        base_url: The base URL of the endpoint.
        path_url: The path of the endpoint.
        method: The HTTP method of the endpoint.
        headers: Headers to send to the endpoint. These do not include an
            ``Authorization`` header; tests add a valid or invalid bearer
            token themselves.
        data: The body to send to the endpoint.
        takes_json_body: Whether the endpoint reads a JSON request body.

    Attributes:
        base_url: The base URL of the endpoint.
        path_url: The path of the endpoint.
        method: The HTTP method of the endpoint.
        headers: Headers to send to the endpoint. These do not include an
            ``Authorization`` header; tests add a valid or invalid bearer
            token themselves.
        data: The body to send to the endpoint.
        takes_json_body: Whether the endpoint reads a JSON request body.
    """

    base_url: str
    path_url: str
    method: str
    headers: Mapping[str, str]
    data: bytes
    takes_json_body: bool

    @beartype
    def send(self) -> Response:
        """Send the request.

        Safe requests use the retry policy supplied by the backend
        adapter. See
        :py:mod:`vws_mock_contract_tests.utils.model_target_retries`.
        """
        return send_with_transient_retries(
            method=self.method,
            send=lambda: _send_request(
                method=self.method,
                url=urljoin(base=self.base_url, url=self.path_url),
                headers=self.headers,
                data=self.data,
            ),
        )
