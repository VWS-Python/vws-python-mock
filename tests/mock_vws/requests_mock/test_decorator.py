"""Tests for decorator through the `requests-mock` backend."""

import uuid
from collections.abc import Callable
from http import HTTPStatus

import httpx
import httpx2
import pytest
import requests
from vws import VuMarkService
from vws.vumark_accept import VuMarkAccept
from vws_auth_tools import rfc_1123_date

from mock_vws import MockVWS
from mock_vws.database import VuMarkDatabase
from mock_vws.target import VuMarkTarget


def test_requests_are_mocked_only_within_the_function(
    unused_local_url: Callable[[], str],
) -> None:
    """Requests to Vuforia are mocked within the decorated function,
    and
    they are not mocked once the decorated function has returned.
    """
    base_vws_url = unused_local_url()
    summary_url = base_vws_url + "/targets/template/instances"

    @MockVWS(base_vws_url=base_vws_url)
    def make_request() -> requests.Response:
        """Make a request to the mocked VWS API."""
        return requests.post(
            url=summary_url,
            headers={
                "Date": rfc_1123_date(),
                "Authorization": "bad_auth_token",
            },
            data=b"",
            timeout=30,
        )

    response = make_request()
    assert response.status_code == HTTPStatus.BAD_REQUEST

    # Nothing is listening on the given address, so this shows that the
    # mocking stops when the decorated function returns.
    with pytest.raises(expected_exception=requests.exceptions.ConnectionError):
        _ = requests.post(url=summary_url, timeout=30)


def test_httpx_requests_are_mocked(
    unused_local_url: Callable[[], str],
) -> None:
    """Requests made with ``httpx`` are mocked within the decorated
    function.
    """
    base_vws_url = unused_local_url()
    summary_url = base_vws_url + "/targets/template/instances"

    @MockVWS(base_vws_url=base_vws_url)
    def make_request() -> httpx.Response:
        """Make a request to the mocked VWS API."""
        return httpx.post(
            url=summary_url,
            headers={
                "Date": rfc_1123_date(),
                "Authorization": "bad_auth_token",
            },
            timeout=30,
        )

    response = make_request()
    assert response.status_code == HTTPStatus.BAD_REQUEST

    with pytest.raises(expected_exception=httpx.ConnectError):
        _ = httpx.post(url=summary_url, timeout=30)


def test_httpx2_requests_are_mocked(
    unused_local_url: Callable[[], str],
) -> None:
    """Requests made with ``httpx2`` are mocked within the decorated
    function.
    """
    base_vws_url = unused_local_url()
    summary_url = base_vws_url + "/targets/template/instances"

    @MockVWS(base_vws_url=base_vws_url)
    def make_request() -> httpx2.Response:
        """Make a request to the mocked VWS API."""
        return httpx2.post(
            url=summary_url,
            headers={
                "Date": rfc_1123_date(),
                "Authorization": "bad_auth_token",
            },
            timeout=30,
        )

    response = make_request()
    assert response.status_code == HTTPStatus.BAD_REQUEST

    with pytest.raises(expected_exception=httpx2.ConnectError):
        _ = httpx2.post(url=summary_url, timeout=30)


def test_arguments_and_return_value() -> None:
    """Arguments are passed to the decorated function, and its return
    value is returned.
    """

    @MockVWS()
    def join(*parts: str, separator: str) -> str:
        """Join the given parts."""
        return separator.join(parts)

    assert join("a", "b", separator="-") == "a-b"


def test_function_metadata_is_preserved() -> None:
    """The decorated function keeps its name and docstring."""

    @MockVWS()
    def my_function() -> None:
        """My docstring."""

    assert my_function.__name__ == "my_function"
    assert my_function.__doc__ == "My docstring."


def test_vumark_database_added_before_decorating() -> None:
    """VuMark databases are available within a decorated function."""
    vumark_target = VuMarkTarget(name="test-target")
    database = VuMarkDatabase(vumark_targets={vumark_target})
    mock = MockVWS()
    mock.add_vumark_database(vumark_database=database)

    @mock
    def generate_vumark_instance() -> bytes:
        """Generate a VuMark instance from the configured database."""
        client = VuMarkService(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
        return client.generate_vumark_instance(
            target_id=vumark_target.target_id,
            instance_id=uuid.uuid4().hex,
            accept=VuMarkAccept.PNG,
        )

    assert generate_vumark_instance().startswith(b"\x89PNG")


def test_vumark_targets_are_restored() -> None:
    """VuMark targets changed during a call of a decorated function
    are put back as they were afterwards, just as Cloud targets
    are.
    """
    vumark_target = VuMarkTarget(name="existing-target")
    database = VuMarkDatabase(vumark_targets={vumark_target})
    mock = MockVWS()
    mock.add_vumark_database(vumark_database=database)

    temporary_target = VuMarkTarget(name="temporary")

    @mock
    def add_temporary_target() -> None:
        """Add a target to the database object directly."""
        database.vumark_targets.add(temporary_target)
        assert database.vumark_targets == {
            vumark_target,
            temporary_target,
        }

    add_temporary_target()
    assert database.vumark_targets == {vumark_target}
