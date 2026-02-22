"""Tests for the usage of the mock for ``httpx`` via ``respx``."""

import socket

import httpx
import pytest
from vws_auth_tools import rfc_1123_date

from mock_vws import MissingSchemeError, MockVWSForHttpx
from mock_vws.database import CloudDatabase, VuMarkDatabase


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
        with MockVWSForHttpx():
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
        unmocked
        addresses are not stopped.
        """
        with (
            MockVWSForHttpx(real_http=True),
            pytest.raises(expected_exception=httpx.ConnectError),
        ):
            _request_unmocked_address()


class TestResponseDelay:
    """Tests for the response delay feature."""

    @staticmethod
    def test_default_no_delay() -> None:
        """By default, there is no response delay."""
        with MockVWSForHttpx():
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
            MockVWSForHttpx(response_delay_seconds=0.5),
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
        with MockVWSForHttpx(response_delay_seconds=0.1):
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
        with MockVWSForHttpx(
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
            MockVWSForHttpx(
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
        with MockVWSForHttpx(
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
        with MockVWSForHttpx(
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
    def test_no_scheme() -> None:
        """An error is raised if a URL is given with no scheme."""
        with pytest.raises(expected_exception=MissingSchemeError) as vws_exc:
            MockVWSForHttpx(base_vws_url="vuforia.vws.example.com")

        expected = (
            'Invalid URL "vuforia.vws.example.com": No scheme supplied. '
            'Perhaps you meant "https://vuforia.vws.example.com".'
        )
        assert str(object=vws_exc.value) == expected
        with pytest.raises(expected_exception=MissingSchemeError) as vwq_exc:
            MockVWSForHttpx(base_vwq_url="vuforia.vwq.example.com")
        expected = (
            'Invalid URL "vuforia.vwq.example.com": No scheme supplied. '
            'Perhaps you meant "https://vuforia.vwq.example.com".'
        )
        assert str(object=vwq_exc.value) == expected


class TestAddDatabase:
    """Tests for adding databases to the mock."""

    @staticmethod
    def test_duplicate_keys() -> None:
        """It is not possible to have multiple databases with matching
        keys.
        """
        database = CloudDatabase(
            server_access_key="1",
            server_secret_key="2",
            client_access_key="3",
            client_secret_key="4",
            database_name="5",
        )

        bad_server_access_key_db = CloudDatabase(server_access_key="1")
        bad_server_secret_key_db = CloudDatabase(server_secret_key="2")
        bad_client_access_key_db = CloudDatabase(client_access_key="3")
        bad_client_secret_key_db = CloudDatabase(client_secret_key="4")
        bad_database_name_db = CloudDatabase(database_name="5")

        server_access_key_conflict_error = (
            "All server access keys must be unique. "
            'There is already a database with the server access key "1".'
        )
        server_secret_key_conflict_error = (
            "All server secret keys must be unique. "
            'There is already a database with the server secret key "2".'
        )
        client_access_key_conflict_error = (
            "All client access keys must be unique. "
            'There is already a database with the client access key "3".'
        )
        client_secret_key_conflict_error = (
            "All client secret keys must be unique. "
            'There is already a database with the client secret key "4".'
        )
        database_name_conflict_error = (
            "All names must be unique. "
            'There is already a database with the name "5".'
        )

        with MockVWSForHttpx() as mock:
            mock.add_cloud_database(cloud_database=database)
            for bad_database, expected_message in (
                (bad_server_access_key_db, server_access_key_conflict_error),
                (bad_server_secret_key_db, server_secret_key_conflict_error),
                (bad_client_access_key_db, client_access_key_conflict_error),
                (bad_client_secret_key_db, client_secret_key_conflict_error),
                (bad_database_name_db, database_name_conflict_error),
            ):
                with pytest.raises(
                    expected_exception=ValueError,
                    match=expected_message + "$",
                ):
                    mock.add_cloud_database(cloud_database=bad_database)

    @staticmethod
    def test_duplicate_vumark_keys() -> None:
        """It is not possible to have multiple databases with matching
        keys,
        including VuMark databases.
        """
        database = VuMarkDatabase(
            server_access_key="1",
            server_secret_key="2",
            database_name="3",
        )

        bad_server_access_key_db = VuMarkDatabase(server_access_key="1")
        bad_server_secret_key_db = VuMarkDatabase(server_secret_key="2")
        bad_database_name_db = VuMarkDatabase(database_name="3")

        server_access_key_conflict_error = (
            "All server access keys must be unique. "
            'There is already a database with the server access key "1".'
        )
        server_secret_key_conflict_error = (
            "All server secret keys must be unique. "
            'There is already a database with the server secret key "2".'
        )
        database_name_conflict_error = (
            "All names must be unique. "
            'There is already a database with the name "3".'
        )

        with MockVWSForHttpx() as mock:
            mock.add_vumark_database(vumark_database=database)
            for bad_database, expected_message in (
                (bad_server_access_key_db, server_access_key_conflict_error),
                (bad_server_secret_key_db, server_secret_key_conflict_error),
                (bad_database_name_db, database_name_conflict_error),
            ):
                with pytest.raises(
                    expected_exception=ValueError,
                    match=expected_message + "$",
                ):
                    mock.add_vumark_database(vumark_database=bad_database)


class TestVWSEndpoints:
    """Tests that VWS endpoints are accessible via httpx."""

    @staticmethod
    def test_database_summary() -> None:
        """The database summary endpoint is accessible via httpx."""
        database = CloudDatabase()
        with MockVWSForHttpx() as mock:
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
