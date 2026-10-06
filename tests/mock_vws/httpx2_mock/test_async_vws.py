"""Tests for `AsyncVWS` through the `httpx2` mock."""

import io

import httpx2
import pytest
from vws import (
    AsyncVWS,
)
from vws.exceptions.vws_exceptions import (
    UnknownTargetError,
)
from vws.reports import TargetStatuses
from vws.transports import AsyncHTTPX2Transport

from mock_vws import MockVWS
from mock_vws.database import CloudDatabase
from tests.mock_vws.httpx2_mock.helpers import run


def test_response_delay_causes_httpx2_timeout() -> None:
    """``httpx2`` timeouts are surfaced through ``AsyncVWS``."""
    database = CloudDatabase()
    calls: list[float] = []

    async def get_summary() -> None:
        """Ask for a database summary report."""
        client = AsyncVWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
            request_timeout_seconds=0.1,
            transport=AsyncHTTPX2Transport(),
        )
        try:
            await client.get_database_summary_report()
        finally:
            await client.aclose()

    with MockVWS(
        response_delay_seconds=5.0,
        sleep_fn=calls.append,
        processing_time_seconds=0,
    ) as mock:
        mock.add_cloud_database(cloud_database=database)
        with pytest.raises(expected_exception=httpx2.ReadTimeout):
            run(coroutine=get_summary())

    assert calls == [0.1]


def test_add_get_and_delete_target(
    image_file_success_state_low_rating: io.BytesIO,
) -> None:
    """A target life cycle works through ``AsyncVWS``."""
    database = CloudDatabase()
    target_name = "async-httpx2-target"

    async def life_cycle() -> str:
        """Add a target, read it back, and delete it.

        Returns:
            The name of the target which was added.
        """
        client = AsyncVWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
            transport=AsyncHTTPX2Transport(),
        )
        try:
            target_id = await client.add_target(
                name=target_name,
                width=1,
                image=image_file_success_state_low_rating,
                application_metadata=None,
                active_flag=True,
            )
            await client.wait_for_target_processed(target_id=target_id)
            target_record = await client.get_target_record(
                target_id=target_id,
            )
            assert target_record.status == TargetStatuses.SUCCESS
            await client.delete_target(target_id=target_id)
            with pytest.raises(expected_exception=UnknownTargetError):
                await client.get_target_record(target_id=target_id)
        finally:
            await client.aclose()
        return target_record.target_record.name

    with MockVWS(processing_time_seconds=0) as mock:
        mock.add_cloud_database(cloud_database=database)
        name = run(coroutine=life_cycle())

    assert name == target_name
