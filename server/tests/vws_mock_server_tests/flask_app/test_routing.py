"""Tests for routing through the Flask app.

Tests for requests which the Flask app does not route.

Signed requests are covered by
``tests/mock_vws/invalid_given_id``, which verifies the
responses against real Vuforia.
"""

from http import HTTPStatus

from mock_vws._flask_server import target_manager as legacy_target_manager
from mock_vws._flask_server import vwq as legacy_vwq
from mock_vws._flask_server import vws as legacy_vws
from vws_mock_server.target_manager import TARGET_MANAGER_FLASK_APP
from vws_mock_server.vwq import CLOUDRECO_FLASK_APP
from vws_mock_server.vws import VWS_FLASK_APP


def test_unauthenticated_unknown_path() -> None:
    """A request to a path which is not routed returns a 404 even
    without credentials.

    The Docker health check relies on this request returning a
    response.
    """
    # Compatibility imports must share the same applications and state.
    assert legacy_vws.VWS_FLASK_APP is VWS_FLASK_APP
    assert legacy_vwq.CLOUDRECO_FLASK_APP is CLOUDRECO_FLASK_APP
    assert (
        legacy_target_manager.TARGET_MANAGER_FLASK_APP
        is TARGET_MANAGER_FLASK_APP
    )
    response = VWS_FLASK_APP.test_client().get("/some-random-endpoint")

    assert response.status_code == HTTPStatus.NOT_FOUND
