"""Tests for routing through the Flask app.

Tests for requests which the Flask app does not route.

Signed requests are covered by
``tests/mock_vws/invalid_given_id``, which verifies the
responses against real Vuforia.
"""

from http import HTTPStatus

import pytest

from vws_mock_server.vws import VWS_FLASK_APP


@pytest.mark.parametrize(
    argnames="path", argvalues=["/unknown", "/summary", "/targets"]
)
def test_removed_or_unknown_route(
    path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Removed cloud routes and unknown paths receive an empty 404."""
    monkeypatch.setitem(
        dic=VWS_FLASK_APP.config,
        name="VWS_MOCK_TERMINATE_WSGI_INPUT",
        value=False,
    )
    with VWS_FLASK_APP.test_client() as client:
        response = client.get(path=path)
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.data == b""
    assert "Content-Type" not in response.headers
