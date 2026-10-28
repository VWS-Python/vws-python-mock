"""Tests for requests which VWS does not serve."""

from http import HTTPMethod, HTTPStatus

from vws_mock_contract_tests.fixtures.credentials import (
    CloudDatabaseCredentials,
)
from vws_mock_contract_tests.invalid_given_id.helpers import (
    send_unrouted_request,
)
from vws_mock_contract_tests.utils.unrouted_requests import UnroutedRequests


def test_unknown_path(
    *,
    vuforia_database: CloudDatabaseCredentials,
    unrouted_requests: UnroutedRequests,
) -> None:
    """A request to a path which is not served returns a 404 with no
    body.
    """
    response = send_unrouted_request(
        send=unrouted_requests.send,
        vuforia_database=vuforia_database,
        method=HTTPMethod.GET,
        request_path="/some-random-endpoint",
    )

    if not unrouted_requests.returns_response:
        # The ``requests``, ``httpx`` and ``httpx2`` backends mock only
        # the paths which they serve, so they give no response at all.
        assert response is None
        return

    assert response is not None
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.body == b""
    assert response.content_type is None
    assert response.content_encoding is None
    assert response.upstream_service_time is None


def test_unknown_method(
    *,
    vuforia_database: CloudDatabaseCredentials,
    unrouted_requests: UnroutedRequests,
) -> None:
    """A request to a served path with a method which that path does
    not serve returns a 404, rather than a 405.
    """
    response = send_unrouted_request(
        send=unrouted_requests.send,
        vuforia_database=vuforia_database,
        method=HTTPMethod.DELETE,
        request_path="/summary",
    )

    if not unrouted_requests.returns_response:
        assert response is None
        return

    assert response is not None
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.content_type == "text/html; charset=UTF-8"
    assert response.content_encoding == "gzip"
    assert response.upstream_service_time is not None
    assert b"<h1>Not Found</h1>" in response.body
    assert b"For request 'DELETE /summary'" in response.body
