"""Tests for routing through the Flask app.

Tests for requests which the Flask app does not route.

Signed requests are covered by
``tests/mock_vws/test_invalid_given_id.py``, which verifies the
responses against real Vuforia.
"""

from http import HTTPStatus

from mock_vws._flask_server.vws import VWS_FLASK_APP


def test_unauthenticated_unknown_path() -> None:
    """A request to a path which is not routed returns a 404 even
    without credentials.

    The Docker health check relies on this request returning a
    response.
    """
    response = VWS_FLASK_APP.test_client().get("/some-random-endpoint")

    assert response.status_code == HTTPStatus.NOT_FOUND
