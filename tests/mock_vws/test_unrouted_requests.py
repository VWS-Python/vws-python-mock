"""Verified fake tests for requests which VWS does not serve.

These cover requests to a path which VWS does not serve, and requests to a
served path with a method which that path does not serve.
"""

from dataclasses import dataclass
from http import HTTPMethod, HTTPStatus

import pytest
import requests
from beartype import beartype
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws._flask_server.vws import VWS_FLASK_APP
from mock_vws.database import CloudDatabase
from tests.mock_vws.fixtures.vuforia_backends import VuforiaBackend

_VWS_HOST = "https://vws.vuforia.com"


@beartype
@dataclass(frozen=True, kw_only=True)
class _UnroutedResponse:
    """The parts of a response to a request which no route serves."""

    status_code: int
    body: bytes
    content_type: str | None


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
        return _UnroutedResponse(
            status_code=test_client_response.status_code,
            body=test_client_response.data,
            content_type=test_client_response.headers.get(
                key="Content-Type",
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
