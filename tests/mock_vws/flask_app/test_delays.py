"""Tests for delays through the Flask app."""

import email.utils
import time

import pytest
import requests

from mock_vws.database import CloudDatabase
from tests.mock_vws.flask_app.helpers import EXAMPLE_URL_FOR_TARGET_MANAGER


class TestResponseDelay:
    """Tests for the response delay feature.

    These tests run through the ``responses`` library, which intercepts
    requests in-process. Because of this, the client ``timeout`` parameter
    is not enforced — the delay blocks but never raises
    ``requests.exceptions.Timeout``. When running the Flask app as a real
    server (e.g. in Docker), the delay causes a genuinely slow HTTP
    response and the ``requests`` client will raise ``Timeout`` on its own.
    """

    DELAY_SECONDS = 0.5

    @staticmethod
    def _make_request() -> None:
        """Make a request to the VWS API."""
        _ = requests.get(
            url="https://vws.vuforia.com/summary",
            headers={
                "Date": email.utils.formatdate(
                    timeval=None,
                    localtime=False,
                    usegmt=True,
                ),
                "Authorization": "bad_auth_token",
            },
            data=b"",
            timeout=30,
        )

    def test_default_no_delay(self) -> None:
        """By default, there is no response delay."""
        database = CloudDatabase()
        databases_url = EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        _ = requests.post(
            url=databases_url, json=database.to_dict(), timeout=30
        )

        start = time.monotonic()
        self._make_request()
        elapsed = time.monotonic() - start
        assert elapsed < self.DELAY_SECONDS

    def test_delay_is_applied(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When response_delay_seconds is set, the response is delayed."""
        monkeypatch.setenv(
            name="RESPONSE_DELAY_SECONDS",
            value=f"{self.DELAY_SECONDS}",
        )
        database = CloudDatabase()
        databases_url = EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
        _ = requests.post(
            url=databases_url, json=database.to_dict(), timeout=30
        )

        start = time.monotonic()
        self._make_request()
        elapsed = time.monotonic() - start
        assert elapsed >= self.DELAY_SECONDS
