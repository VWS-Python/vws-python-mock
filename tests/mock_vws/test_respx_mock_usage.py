"""Tests for ``MockVWS`` intercepting ``httpx`` requests."""

import json
import socket
import uuid
from http import HTTPMethod, HTTPStatus

import httpx
import pytest
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws import MockVWS
from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.target import VuMarkTarget


def _request_unmocked_address() -> None:
    """Make a request using ``httpx`` to an unmocked, free local address.

    Raises:
        Exception: A connection error is expected, as there is nothing
            to connect to.
    """
    sock = socket.socket()
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    httpx.get(url=f"http://localhost:{port}", timeout=30)


def _request_mocked_address() -> None:
    """Make a request using ``httpx`` to a mocked Vuforia endpoint."""
    httpx.get(
        url="https://vws.vuforia.com/summary",
        headers={
            "Date": rfc_1123_date(),
            "Authorization": "bad_auth_token",
        },
        timeout=30,
    )


class TestRealHTTP:
    """Tests for making requests to mocked and unmocked addresses."""

    @staticmethod
    def test_default() -> None:
        """By default, the mock stops any requests made with ``httpx`` to
        non-Vuforia addresses, but not to mocked Vuforia endpoints.
        """
        with MockVWS():
            with pytest.raises(expected_exception=httpx.ConnectError):
                _request_unmocked_address()

            # No exception is raised when making a request to a mocked
            # endpoint.
            _request_mocked_address()

        # The mocking stops when the context manager stops.
        with pytest.raises(expected_exception=httpx.ConnectError):
            _request_unmocked_address()

    @staticmethod
    def test_real_http() -> None:
        """When the ``real_http`` parameter is ``True``, requests to
        unmocked addresses are not stopped.
        """
        with (
            MockVWS(real_http=True),
            pytest.raises(expected_exception=httpx.ConnectError),
        ):
            _request_unmocked_address()


class TestResponseDelay:
    """Tests for the response delay feature."""

    @staticmethod
    def test_default_no_delay() -> None:
        """By default, there is no response delay."""
        with MockVWS():
            response = httpx.get(
                url="https://vws.vuforia.com/summary",
                headers={
                    "Date": rfc_1123_date(),
                    "Authorization": "bad_auth_token",
                },
                timeout=0.5,
            )
            assert response.status_code is not None

    @staticmethod
    def test_delay_causes_timeout() -> None:
        """When ``response_delay_seconds`` is set higher than the client
        timeout, a ``ReadTimeout`` exception is raised.
        """
        with (
            MockVWS(response_delay_seconds=0.5),
            pytest.raises(expected_exception=httpx.ReadTimeout),
        ):
            httpx.get(
                url="https://vws.vuforia.com/summary",
                headers={
                    "Date": rfc_1123_date(),
                    "Authorization": "bad_auth_token",
                },
                timeout=0.1,
            )

    @staticmethod
    def test_delay_allows_completion() -> None:
        """When ``response_delay_seconds`` is set lower than the client
        timeout, the request completes successfully.
        """
        with MockVWS(response_delay_seconds=0.1):
            response = httpx.get(
                url="https://vws.vuforia.com/summary",
                headers={
                    "Date": rfc_1123_date(),
                    "Authorization": "bad_auth_token",
                },
                timeout=2.0,
            )
            assert response.status_code is not None

    @staticmethod
    def test_custom_sleep_fn_called_on_delay() -> None:
        """When a custom ``sleep_fn`` is provided, it is called instead of
        ``time.sleep`` for the non-timeout delay path.
        """
        calls: list[float] = []
        with MockVWS(
            response_delay_seconds=5.0,
            sleep_fn=calls.append,
        ):
            httpx.get(
                url="https://vws.vuforia.com/summary",
                headers={
                    "Date": rfc_1123_date(),
                    "Authorization": "bad_auth_token",
                },
                timeout=30,
            )
        assert calls == [5.0]

    @staticmethod
    def test_custom_sleep_fn_called_on_timeout() -> None:
        """When a custom ``sleep_fn`` is provided, it is called with the
        effective timeout when the delay exceeds it.
        """
        calls: list[float] = []
        with (
            MockVWS(
                response_delay_seconds=5.0,
                sleep_fn=calls.append,
            ),
            pytest.raises(expected_exception=httpx.ReadTimeout),
        ):
            httpx.get(
                url="https://vws.vuforia.com/summary",
                headers={
                    "Date": rfc_1123_date(),
                    "Authorization": "bad_auth_token",
                },
                timeout=1.0,
            )
        assert calls == [1.0]


class TestCustomBaseURLs:
    """Tests for using custom base URLs."""

    @staticmethod
    def test_custom_base_vws_url() -> None:
        """It is possible to use a custom base VWS URL."""
        with MockVWS(
            base_vws_url="https://vuforia.vws.example.com",
            real_http=False,
        ):
            with pytest.raises(expected_exception=httpx.ConnectError):
                httpx.get(url="https://vws.vuforia.com/summary", timeout=30)

            httpx.get(
                url="https://vuforia.vws.example.com/summary",
                timeout=30,
            )
            httpx.post(
                url="https://cloudreco.vuforia.com/v1/query",
                timeout=30,
            )

    @staticmethod
    def test_custom_base_vwq_url() -> None:
        """It is possible to use a custom base cloud recognition URL."""
        with MockVWS(
            base_vwq_url="https://vuforia.vwq.example.com",
            real_http=False,
        ):
            with pytest.raises(expected_exception=httpx.ConnectError):
                httpx.post(
                    url="https://cloudreco.vuforia.com/v1/query",
                    timeout=30,
                )

            httpx.post(
                url="https://vuforia.vwq.example.com/v1/query",
                timeout=30,
            )
            httpx.get(
                url="https://vws.vuforia.com/summary",
                timeout=30,
            )

    @staticmethod
    def test_custom_base_vws_url_with_path_prefix() -> None:
        """A custom base VWS URL with a path prefix intercepts at the
        prefix.
        """
        with MockVWS(
            base_vws_url="https://vuforia.vws.example.com/prefix",
            real_http=False,
        ):
            with pytest.raises(expected_exception=httpx.ConnectError):
                httpx.get(
                    url="https://vuforia.vws.example.com/summary",
                    timeout=30,
                )

            httpx.get(
                url="https://vuforia.vws.example.com/prefix/summary",
                timeout=30,
            )

    @staticmethod
    def test_custom_base_vwq_url_with_path_prefix() -> None:
        """A custom base VWQ URL with a path prefix intercepts at the
        prefix.
        """
        with MockVWS(
            base_vwq_url="https://vuforia.vwq.example.com/prefix",
            real_http=False,
        ):
            with pytest.raises(expected_exception=httpx.ConnectError):
                httpx.post(
                    url="https://vuforia.vwq.example.com/v1/query",
                    timeout=30,
                )

            httpx.post(
                url="https://vuforia.vwq.example.com/prefix/v1/query",
                timeout=30,
            )

    @staticmethod
    def test_vws_operations_work_with_path_prefix() -> None:
        """VWS API operations work correctly with a base URL path
        prefix.
        """
        database = CloudDatabase()
        base_vws_url = "https://vuforia.vws.example.com/prefix"

        with MockVWS(base_vws_url=base_vws_url) as mock:
            mock.add_cloud_database(cloud_database=database)

            request_path = "/targets"
            date = rfc_1123_date()
            auth = authorization_header(
                access_key=database.server_access_key,
                secret_key=database.server_secret_key,
                method="GET",
                content=b"",
                content_type="",
                date=date,
                request_path=request_path,
            )
            response = httpx.get(
                url=base_vws_url + request_path,
                headers={
                    "Authorization": auth,
                    "Date": date,
                },
                timeout=30,
            )

        assert response.status_code == HTTPStatus.OK
        response_json = response.json()
        assert response_json["result_code"] == "Success"
        assert response_json["results"] == []


class TestVWSEndpoints:
    """Tests that VWS endpoints are accessible via httpx."""

    @staticmethod
    def test_database_summary() -> None:
        """The database summary endpoint is accessible via httpx."""
        database = CloudDatabase()
        with MockVWS() as mock:
            mock.add_cloud_database(cloud_database=database)
            response = httpx.get(
                url="https://vws.vuforia.com/summary",
                headers={
                    "Date": rfc_1123_date(),
                    "Authorization": "bad_auth_token",
                },
                timeout=30,
            )
        # We just verify we get a response (auth will fail but endpoint works)
        assert response.status_code is not None

    @staticmethod
    def test_vumark_bytes_response() -> None:
        """The VuMark endpoint returns bytes content via httpx."""
        vumark_target = VuMarkTarget(name="test-target")
        database = VuMarkDatabase(vumark_targets={vumark_target})
        target_id = vumark_target.target_id
        request_path = f"/targets/{target_id}/instances"
        content_type = "application/json"
        content = json.dumps(obj={"instance_id": uuid.uuid4().hex}).encode(
            encoding="utf-8"
        )
        date = rfc_1123_date()
        auth = authorization_header(
            access_key=database.server_access_key,
            secret_key=database.server_secret_key,
            method=HTTPMethod.POST,
            content=content,
            content_type=content_type,
            date=date,
            request_path=request_path,
        )
        with MockVWS() as mock:
            mock.add_vumark_database(vumark_database=database)
            response = httpx.post(
                url="https://vws.vuforia.com" + request_path,
                headers={
                    "Accept": "image/png",
                    "Authorization": auth,
                    "Content-Length": str(object=len(content)),
                    "Content-Type": content_type,
                    "Date": date,
                },
                content=content,
                timeout=30,
            )
        assert response.status_code == HTTPStatus.OK
