"""Tests for requests which name something that VWS does not serve.

These cover an invalid target ID given to an endpoint which requires one, a
path which VWS does not serve, and a served path with a method which that
path does not serve.

The tests for paths and methods live here, rather than in a file of their
own, because every entry in the CI test matrix uses one of the credentials
files in ``secrets.tar.gpg``, and there are exactly as many of those files as
there are entries.
"""

import gzip
from dataclasses import dataclass
from http import HTTPMethod, HTTPStatus

import pytest
import requests
from beartype import beartype
from vws import VWS
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws._constants import ResultCodes
from mock_vws._flask_server.vws import VWS_FLASK_APP
from mock_vws.database import CloudDatabase
from tests.mock_vws.fixtures.vuforia_backends import VuforiaBackend
from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.assertions import assert_vws_failure
from tests.mock_vws.utils.too_many_requests import handle_server_errors

_VWS_HOST = "https://vws.vuforia.com"


@beartype
@dataclass(frozen=True, kw_only=True)
class _UnroutedResponse:
    """The parts of a response to a request which no route serves."""

    status_code: int
    body: bytes
    content_type: str | None
    content_encoding: str | None
    upstream_service_time: str | None


@beartype
def _send_unrouted_request(
    *,
    backend: VuforiaBackend,
    vuforia_database: CloudDatabase,
    method: HTTPMethod,
    request_path: str,
) -> _UnroutedResponse | None:
    """Send a signed request which no route serves and return the response.

    ``None`` is returned when the backend refuses the connection rather than
    returning a response.
    """
    date = rfc_1123_date()
    headers = {
        "Authorization": authorization_header(
            access_key=vuforia_database.server_access_key,
            secret_key=vuforia_database.server_secret_key,
            method=method,
            content=b"",
            content_type="",
            date=date,
            request_path=request_path,
        ),
        "Date": date,
    }

    if backend == VuforiaBackend.DOCKER_IN_MEMORY:
        # The ``responses`` library intercepts only the paths and methods
        # which the Flask app routes, so requests to any other path never
        # reach the app. A running container serves every path, so we drive
        # the app with its own test client.
        test_client_response = VWS_FLASK_APP.test_client().open(
            request_path,
            method=method,
            headers=headers,
        )
        response_body = test_client_response.data
        content_encoding = test_client_response.headers.get(
            key="Content-Encoding",
        )
        if content_encoding == "gzip":
            response_body = gzip.decompress(data=response_body)
        return _UnroutedResponse(
            status_code=test_client_response.status_code,
            body=response_body,
            content_type=test_client_response.headers.get(
                key="Content-Type",
            ),
            content_encoding=content_encoding,
            upstream_service_time=test_client_response.headers.get(
                key="x-envoy-upstream-service-time",
            ),
        )

    try:
        response = requests.request(
            method=method,
            url=_VWS_HOST + request_path,
            headers=headers,
            timeout=30,
        )
    except requests.exceptions.ConnectionError:
        return None

    return _UnroutedResponse(
        status_code=response.status_code,
        body=response.content,
        content_type=response.headers.get("Content-Type"),
        content_encoding=response.headers.get("Content-Encoding"),
        upstream_service_time=response.headers.get(
            "x-envoy-upstream-service-time",
        ),
    )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestInvalidGivenID:
    """
    Tests for giving an invalid ID to endpoints which require a target
    ID to be
    given.
    """

    @staticmethod
    def test_not_real_id(
        *,
        vws_client: VWS,
        endpoint: Endpoint,
        target_id: str,
    ) -> None:
        """
        A `NOT_FOUND` error is returned when an endpoint is given a
        target ID
        of a target which does not exist.
        """
        # This shared check only covers endpoints that end in target_id,
        # such as /targets/{target_id}. Endpoints with trailing segments
        # are covered by endpoint-specific tests.
        if not endpoint.path_url.endswith(target_id):
            return

        vws_client.delete_target(target_id=target_id)

        response = endpoint.send()

        handle_server_errors(response=response)

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.NOT_FOUND,
            result_code=ResultCodes.UNKNOWN_TARGET,
        )


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestUnroutedRequests:
    """Tests for requests which VWS does not serve."""

    @staticmethod
    def test_unknown_path(
        *,
        vuforia_database: CloudDatabase,
        verify_mock_vuforia: VuforiaBackend,
    ) -> None:
        """A request to a path which is not served returns a 404 with no
        body.
        """
        response = _send_unrouted_request(
            backend=verify_mock_vuforia,
            vuforia_database=vuforia_database,
            method=HTTPMethod.GET,
            request_path="/some-random-endpoint",
        )

        if verify_mock_vuforia == VuforiaBackend.MOCK:
            # The ``requests`` and ``httpx`` backends mock only the paths
            # which they serve, so they give no response at all.
            assert response is None
            return

        assert response is not None
        assert response.status_code == HTTPStatus.NOT_FOUND
        assert response.body == b""
        assert response.content_type is None
        assert response.content_encoding is None
        assert response.upstream_service_time is None

    @staticmethod
    def test_unknown_method(
        *,
        vuforia_database: CloudDatabase,
        verify_mock_vuforia: VuforiaBackend,
    ) -> None:
        """A request to a served path with a method which that path does
        not serve returns a 404, rather than a 405.
        """
        response = _send_unrouted_request(
            backend=verify_mock_vuforia,
            vuforia_database=vuforia_database,
            method=HTTPMethod.DELETE,
            request_path="/summary",
        )

        if verify_mock_vuforia == VuforiaBackend.MOCK:
            assert response is None
            return

        assert response is not None
        assert response.status_code == HTTPStatus.NOT_FOUND
        assert response.content_type == "text/html; charset=UTF-8"
        assert response.content_encoding == "gzip"
        assert response.upstream_service_time is not None
        assert b"<h1>Not Found</h1>" in response.body
        assert b"For request 'DELETE /summary'" in response.body
