"""Tests for network through the `requests-mock` backend."""

from collections.abc import Callable
from http import HTTPStatus

import httpx
import httpx2
import pytest
import requests
from beartype import beartype
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws import MissingSchemeError, MockVWS
from mock_vws.database import CloudDatabase


@beartype
def request_unmocked_address(unused_local_url: Callable[[], str]) -> None:
    """Make a request, using `requests` to an unmocked, free local address.

    Raises:
        requests.exceptions.ConnectionError: This is expected as there is
            nothing to connect to.
        requests.exceptions.ConnectionError: This request is being made in the
            context of a ``responses`` mock which does not mock local
            addresses.
    """
    _ = requests.get(url=unused_local_url(), timeout=30)


@beartype
def request_mocked_address() -> None:
    """
    Make a request, using `requests` to an address that is mocked by
    `MockVWS`.
    """
    _ = requests.get(
        url="https://vws.vuforia.com/summary",
        headers={
            "Date": rfc_1123_date(),
            "Authorization": "bad_auth_token",
        },
        data=b"",
        timeout=30,
    )


def test_default(unused_local_url: Callable[[], str]) -> None:
    """
    By default, the mock stops any requests made with `requests` to
    non-
    Vuforia addresses, but not to mocked Vuforia endpoints.
    """
    with MockVWS():
        with pytest.raises(
            expected_exception=requests.exceptions.ConnectionError
        ):
            request_unmocked_address(unused_local_url=unused_local_url)

        # No exception is raised when making a request to a mocked
        # endpoint.
        request_mocked_address()

    # The mocking stops when the context manager stops.
    with pytest.raises(expected_exception=requests.exceptions.ConnectionError):
        request_unmocked_address(unused_local_url=unused_local_url)


def test_real_http(unused_local_url: Callable[[], str]) -> None:
    """
    When the `real_http` parameter given to the context manager is
    set to
    `True`, requests made to unmocked addresses are not stopped.
    """
    with (
        MockVWS(real_http=True),
        pytest.raises(expected_exception=requests.exceptions.ConnectionError),
    ):
        request_unmocked_address(unused_local_url=unused_local_url)


def test_custom_base_vws_url() -> None:
    """It is possible to use a custom base VWS URL."""
    with MockVWS(
        base_vws_url="https://vuforia.vws.example.com",
        real_http=False,
    ):
        with pytest.raises(
            expected_exception=requests.exceptions.ConnectionError
        ):
            _ = requests.get(url="https://vws.vuforia.com/summary", timeout=30)

        _ = requests.get(
            url="https://vuforia.vws.example.com/summary",
            timeout=30,
        )
        _ = requests.post(
            url="https://cloudreco.vuforia.com/v1/query",
            timeout=30,
        )


def test_custom_base_vwq_url() -> None:
    """It is possible to use a custom base cloud recognition URL."""
    with MockVWS(
        base_vwq_url="https://vuforia.vwq.example.com",
        real_http=False,
    ):
        with pytest.raises(
            expected_exception=requests.exceptions.ConnectionError
        ):
            _ = requests.post(
                url="https://cloudreco.vuforia.com/v1/query",
                timeout=30,
            )

        _ = requests.post(
            url="https://vuforia.vwq.example.com/v1/query",
            timeout=30,
        )
        _ = requests.get(
            url="https://vws.vuforia.com/summary",
            timeout=30,
        )


def test_custom_base_vws_url_with_path_prefix() -> None:
    """A custom base VWS URL with a path prefix intercepts at the
    prefix.
    """
    with MockVWS(
        base_vws_url="https://vuforia.vws.example.com/prefix",
        real_http=False,
    ):
        with pytest.raises(
            expected_exception=requests.exceptions.ConnectionError
        ):
            _ = requests.get(
                url="https://vuforia.vws.example.com/summary",
                timeout=30,
            )

        _ = requests.get(
            url="https://vuforia.vws.example.com/prefix/summary",
            timeout=30,
        )


def test_custom_base_vwq_url_with_path_prefix() -> None:
    """A custom base VWQ URL with a path prefix intercepts at the
    prefix.
    """
    with MockVWS(
        base_vwq_url="https://vuforia.vwq.example.com/prefix",
        real_http=False,
    ):
        with pytest.raises(
            expected_exception=requests.exceptions.ConnectionError
        ):
            _ = requests.post(
                url="https://vuforia.vwq.example.com/v1/query",
                timeout=30,
            )

        _ = requests.post(
            url="https://vuforia.vwq.example.com/prefix/v1/query",
            timeout=30,
        )


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
        response = requests.get(
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


def test_no_scheme() -> None:
    """An error if raised if a URL is given with no scheme."""
    with pytest.raises(expected_exception=MissingSchemeError) as vws_exc:
        _ = MockVWS(base_vws_url="vuforia.vws.example.com")

    expected = (
        'Invalid URL "vuforia.vws.example.com": No scheme supplied. '
        'Perhaps you meant "https://vuforia.vws.example.com".'
    )
    assert str(object=vws_exc.value) == expected
    with pytest.raises(expected_exception=MissingSchemeError) as vwq_exc:
        _ = MockVWS(base_vwq_url="vuforia.vwq.example.com")
    expected = (
        'Invalid URL "vuforia.vwq.example.com": No scheme supplied. '
        'Perhaps you meant "https://vuforia.vwq.example.com".'
    )
    assert str(object=vwq_exc.value) == expected


def test_httpx_vuforia_endpoint_intercepted() -> None:
    """``MockVWS`` intercepts ``httpx`` requests to Vuforia
    endpoints.
    """
    with MockVWS():
        response = httpx.get(
            url="https://vws.vuforia.com/summary",
            headers={
                "Date": rfc_1123_date(),
                "Authorization": "bad_auth_token",
            },
            timeout=30,
        )
    assert response.status_code is not None


def test_httpx_unmocked_address_blocked(
    unused_local_url: Callable[[], str],
) -> None:
    """``MockVWS`` blocks ``httpx`` requests to non-Vuforia
    addresses.
    """
    with MockVWS(), pytest.raises(expected_exception=httpx.ConnectError):
        _ = httpx.get(url=unused_local_url(), timeout=30)


def test_httpx_real_http(unused_local_url: Callable[[], str]) -> None:
    """When ``real_http=True``, ``httpx`` requests to non-Vuforia
    addresses are not blocked.
    """
    with (
        MockVWS(real_http=True),
        pytest.raises(expected_exception=httpx.ConnectError),
    ):
        _ = httpx.get(url=unused_local_url(), timeout=30)


def test_httpx2_vuforia_endpoint_intercepted() -> None:
    """``MockVWS`` intercepts ``httpx2`` requests to Vuforia
    endpoints.
    """
    with MockVWS():
        response = httpx2.get(
            url="https://vws.vuforia.com/summary",
            headers={
                "Date": rfc_1123_date(),
                "Authorization": "bad_auth_token",
            },
            timeout=30,
        )
    assert response.status_code is not None


def test_httpx2_client_made_before_start_intercepted() -> None:
    """A client which was made before the mock started is
    intercepted.
    """
    with httpx2.Client() as client, MockVWS():
        response = client.get(
            url="https://vws.vuforia.com/summary",
            headers={
                "Date": rfc_1123_date(),
                "Authorization": "bad_auth_token",
            },
            timeout=30,
        )
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_httpx2_unmocked_address_blocked(
    unused_local_url: Callable[[], str],
) -> None:
    """``MockVWS`` blocks ``httpx2`` requests to non-Vuforia
    addresses.
    """
    with MockVWS(), pytest.raises(expected_exception=httpx2.ConnectError):
        _ = httpx2.get(url=unused_local_url(), timeout=30)


def test_httpx2_real_http(unused_local_url: Callable[[], str]) -> None:
    """When ``real_http=True``, ``httpx2`` requests to non-Vuforia
    addresses are not blocked.
    """
    with (
        MockVWS(real_http=True),
        pytest.raises(expected_exception=httpx2.ConnectError),
    ):
        _ = httpx2.get(url=unused_local_url(), timeout=30)
