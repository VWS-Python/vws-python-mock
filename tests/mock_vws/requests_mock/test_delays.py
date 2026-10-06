"""Tests for delays through the `requests-mock` backend."""

import io

import pytest
import requests
from vws_auth_tools import rfc_1123_date

from mock_vws import MockVWS
from mock_vws.database import CloudDatabase
from tests.mock_vws.utils.usage_test_helpers import (
    processing_time_seconds,
)


def test_default_no_delay() -> None:
    """By default, there is no response delay."""
    with MockVWS():
        # With a very short timeout, the request should still succeed
        # because there is no delay
        response = requests.get(
            url="https://vws.vuforia.com/summary",
            headers={
                "Date": rfc_1123_date(),
                "Authorization": "bad_auth_token",
            },
            data=b"",
            timeout=0.5,
        )
        # We just care that no timeout occurred, not the response content
        assert response.status_code is not None


def test_delay_causes_timeout() -> None:
    """
    When response_delay_seconds is set higher than the client
    timeout,
    a Timeout exception is raised.
    """
    with (
        MockVWS(response_delay_seconds=0.5),
        pytest.raises(expected_exception=requests.exceptions.Timeout),
    ):
        _ = requests.get(
            url="https://vws.vuforia.com/summary",
            headers={
                "Date": rfc_1123_date(),
                "Authorization": "bad_auth_token",
            },
            data=b"",
            timeout=0.1,
        )


def test_delay_allows_completion() -> None:
    """
    When response_delay_seconds is set lower than the client
    timeout,
    the request completes successfully.
    """
    with MockVWS(response_delay_seconds=0.1):
        # This should succeed because timeout > delay
        response = requests.get(
            url="https://vws.vuforia.com/summary",
            headers={
                "Date": rfc_1123_date(),
                "Authorization": "bad_auth_token",
            },
            data=b"",
            timeout=2.0,
        )
        assert response.status_code is not None


def test_delay_without_timeout() -> None:
    """A request without a timeout waits for the configured delay."""
    calls: list[float] = []
    with MockVWS(
        response_delay_seconds=0.1,
        sleep_fn=calls.append,
    ):
        # Omitting the timeout is the behavior under test.
        # pylint: disable-next=missing-timeout
        response = requests.get(  # noqa: S113
            url="https://vws.vuforia.com/summary",
            headers={
                "Date": rfc_1123_date(),
                "Authorization": "bad_auth_token",
            },
            data=b"",
        )

    assert response.status_code is not None
    assert calls == [0.1]


def test_delay_with_tuple_timeout() -> None:
    """
    The response delay works correctly with tuple timeouts
    (connect_timeout, read_timeout).
    """
    with (
        MockVWS(response_delay_seconds=0.5),
        pytest.raises(expected_exception=requests.exceptions.Timeout),
    ):
        # Tuple timeout: (connect_timeout, read_timeout)
        # The read timeout (0.1) is less than the delay (0.5)
        _ = requests.get(
            url="https://vws.vuforia.com/summary",
            headers={
                "Date": rfc_1123_date(),
                "Authorization": "bad_auth_token",
            },
            data=b"",
            timeout=(5.0, 0.1),
        )


def test_custom_sleep_fn_called_on_delay() -> None:
    """
    An integer delay is passed to a custom ``sleep_fn`` instead of
    ``time.sleep`` on the non-timeout path.
    """
    calls: list[float] = []
    with MockVWS(
        response_delay_seconds=5,
        sleep_fn=calls.append,
    ):
        _ = requests.get(
            url="https://vws.vuforia.com/summary",
            headers={
                "Date": rfc_1123_date(),
                "Authorization": "bad_auth_token",
            },
            data=b"",
            timeout=30,
        )
    assert calls == [5]


def test_custom_sleep_fn_called_on_timeout() -> None:
    """
    When a custom ``sleep_fn`` is provided, it is called instead of
    ``time.sleep`` for the timeout path.
    """
    calls: list[float] = []
    with (
        MockVWS(
            response_delay_seconds=5.0,
            sleep_fn=calls.append,
        ),
        pytest.raises(expected_exception=requests.exceptions.Timeout),
    ):
        _ = requests.get(
            url="https://vws.vuforia.com/summary",
            headers={
                "Date": rfc_1123_date(),
                "Authorization": "bad_auth_token",
            },
            data=b"",
            timeout=1.0,
        )
    # sleep_fn should have been called with the effective timeout
    assert calls == [1.0]


class TestProcessingTime:
    """Tests for the time taken to process targets in the mock."""

    # There is a race condition in this test type - if tests start to
    # fail, consider increasing the leeway.
    LEEWAY = 1.0

    def test_default(self, image_file_failed_state: io.BytesIO) -> None:
        """By default, targets in the mock takes 2 seconds to be processed."""
        database = CloudDatabase()
        with MockVWS() as mock:
            mock.add_cloud_database(cloud_database=database)
            time_taken = processing_time_seconds(
                vuforia_database=database,
                image=image_file_failed_state,
            )

        expected = 2
        assert expected - self.LEEWAY < time_taken < expected + self.LEEWAY

    def test_custom(self, image_file_failed_state: io.BytesIO) -> None:
        """It is possible to set a custom processing time."""
        database = CloudDatabase()
        seconds = 5
        with MockVWS(processing_time_seconds=seconds) as mock:
            mock.add_cloud_database(cloud_database=database)
            time_taken = processing_time_seconds(
                vuforia_database=database,
                image=image_file_failed_state,
            )

        expected = seconds
        assert expected - self.LEEWAY < time_taken < expected + self.LEEWAY
