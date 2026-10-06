"""Tests for `VWS` through the `respx` mock."""

import io
from http import HTTPStatus

import httpx
import pytest
from vws import VWS
from vws.exceptions.vws_exceptions import UnknownTargetError
from vws.reports import TargetStatuses
from vws.transports import HTTPXTransport

from mock_vws import MockVWS
from mock_vws.database import CloudDatabase


def test_response_delay_causes_httpx_timeout() -> None:
    """``httpx`` timeouts are surfaced through ``VWS``."""
    database = CloudDatabase()
    calls: list[float] = []

    with MockVWS(
        response_delay_seconds=5.0,
        sleep_fn=calls.append,
        processing_time_seconds=0,
    ) as mock:
        mock.add_cloud_database(cloud_database=database)
        client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
            request_timeout_seconds=0.1,
            transport=HTTPXTransport(),
        )
        with pytest.raises(expected_exception=httpx.ReadTimeout):
            _ = client.get_database_summary_report()

    assert calls == [0.1]


def test_custom_base_vws_url_with_path_prefix() -> None:
    """``VWS`` works with a custom VWS base URL path prefix."""
    database = CloudDatabase()
    base_vws_url = "https://vuforia.vws.example.com/prefix"

    with MockVWS(base_vws_url=base_vws_url) as mock:
        mock.add_cloud_database(cloud_database=database)
        client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
            base_vws_url=base_vws_url,
            transport=HTTPXTransport(),
        )
        report = client.get_database_summary_report()
        database_name = report.name

    assert database_name == database.database_name


def test_add_get_and_delete_target(
    image_file_success_state_low_rating: io.BytesIO,
) -> None:
    """A target life cycle works through ``VWS``."""
    database = CloudDatabase()
    target_name = "async-target"

    with MockVWS(processing_time_seconds=0) as mock:
        mock.add_cloud_database(cloud_database=database)
        client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
            transport=HTTPXTransport(),
        )
        target_id = client.add_target(
            name=target_name,
            width=1,
            image=image_file_success_state_low_rating,
            application_metadata=None,
            active_flag=True,
        )
        client.wait_for_target_processed(target_id=target_id)
        target_record = client.get_target_record(target_id=target_id)
        assert target_record.status == TargetStatuses.SUCCESS
        assert target_record.target_record.name == target_name

        client.delete_target(target_id=target_id)

        with pytest.raises(expected_exception=UnknownTargetError):
            _ = client.get_target_record(target_id=target_id)


def test_nested_mocks() -> None:
    """A mock inside another mock leaves the outer one working.

    The innermost mock is the only one which answers while it is
    running, which is what the ``requests`` and ``httpx2`` backends do
    too, and the outer mock answers again once the inner one has
    stopped.
    """
    outer_url = "https://vws.vuforia.com/summary"
    inner_url = "https://vuforia.vws.example.com/summary"

    with MockVWS():
        with MockVWS(base_vws_url="https://vuforia.vws.example.com"):
            inner_response = httpx.get(url=inner_url, timeout=30)
            with pytest.raises(expected_exception=httpx.ConnectError):
                _ = httpx.get(url=outer_url, timeout=30)
        outer_response = httpx.get(url=outer_url, timeout=30)

        with pytest.raises(expected_exception=httpx.ConnectError):
            _ = httpx.get(url=inner_url, timeout=30)

    assert inner_response.status_code == HTTPStatus.UNAUTHORIZED
    assert outer_response.status_code == HTTPStatus.UNAUTHORIZED
