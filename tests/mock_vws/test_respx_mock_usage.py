"""Tests for ``MockVWS`` intercepting ``httpx`` via asynchronous ``vws``
clients.
"""

import asyncio
import io
import uuid

import httpx
import pytest
from vws import AsyncCloudRecoService, AsyncVuMarkService, AsyncVWS
from vws.exceptions.vws_exceptions import UnknownTargetError
from vws.reports import TargetStatuses
from vws.vumark_accept import VuMarkAccept

from mock_vws import MockVWS
from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.image_matchers import ExactMatcher
from mock_vws.target import VuMarkTarget


class TestAsyncVWS:
    """Asynchronous ``vws-python`` client usage through the mock."""

    @staticmethod
    def test_response_delay_causes_httpx_timeout() -> None:
        """``httpx`` timeouts are surfaced through ``AsyncVWS``."""
        database = CloudDatabase()
        calls: list[float] = []

        async def run_test() -> None:
            """Trigger a timed request through the client."""
            async with AsyncVWS(
                server_access_key=database.server_access_key,
                server_secret_key=database.server_secret_key,
                request_timeout_seconds=0.1,
            ) as client:
                await client.get_database_summary_report()

        with MockVWS(
            response_delay_seconds=5.0,
            sleep_fn=calls.append,
            processing_time_seconds=0,
        ) as mock:
            mock.add_cloud_database(cloud_database=database)
            with pytest.raises(expected_exception=httpx.ReadTimeout):
                asyncio.run(run_test())

        assert calls == [0.1]

    @staticmethod
    def test_custom_base_vws_url_with_path_prefix() -> None:
        """``AsyncVWS`` works with a custom VWS base URL path prefix."""
        database = CloudDatabase()
        base_vws_url = "https://vuforia.vws.example.com/prefix"

        async def run_test() -> str:
            """Return the database name via the custom base URL."""
            async with AsyncVWS(
                server_access_key=database.server_access_key,
                server_secret_key=database.server_secret_key,
                base_vws_url=base_vws_url,
            ) as client:
                report = await client.get_database_summary_report()
            return report.name

        with MockVWS(base_vws_url=base_vws_url) as mock:
            mock.add_cloud_database(cloud_database=database)
            database_name = asyncio.run(run_test())

        assert database_name == database.database_name

    @staticmethod
    def test_add_get_and_delete_target(
        image_file_success_state_low_rating: io.BytesIO,
    ) -> None:
        """A target life cycle works through ``AsyncVWS``."""
        database = CloudDatabase()
        target_name = "async-target"

        async def run_test() -> None:
            """Exercise the target life cycle."""
            async with AsyncVWS(
                server_access_key=database.server_access_key,
                server_secret_key=database.server_secret_key,
            ) as client:
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
                assert target_record.target_record.name == target_name

                await client.delete_target(target_id=target_id)

                with pytest.raises(expected_exception=UnknownTargetError):
                    await client.get_target_record(target_id=target_id)

        with MockVWS(processing_time_seconds=0) as mock:
            mock.add_cloud_database(cloud_database=database)
            asyncio.run(run_test())


class TestAsyncCloudRecoService:
    """Asynchronous cloud query usage through the mock."""

    @staticmethod
    def test_query_returns_match(high_quality_image: io.BytesIO) -> None:
        """``AsyncCloudRecoService`` returns a match via the mock."""
        database = CloudDatabase()

        async def run_test() -> None:
            """Add a target and query it using the clients."""
            async with (
                AsyncVWS(
                    server_access_key=database.server_access_key,
                    server_secret_key=database.server_secret_key,
                ) as vws_client,
                AsyncCloudRecoService(
                    client_access_key=database.client_access_key,
                    client_secret_key=database.client_secret_key,
                ) as query_client,
            ):
                target_id = await vws_client.add_target(
                    name="query-target",
                    width=1,
                    image=high_quality_image,
                    application_metadata=None,
                    active_flag=True,
                )
                await vws_client.wait_for_target_processed(target_id=target_id)
                results = await query_client.query(image=high_quality_image)
                assert [result.target_id for result in results] == [target_id]

        with MockVWS(
            processing_time_seconds=0,
            query_match_checker=ExactMatcher(),
        ) as mock:
            mock.add_cloud_database(cloud_database=database)
            asyncio.run(run_test())


class TestAsyncVuMarkService:
    """Asynchronous VuMark generation usage through the mock."""

    @staticmethod
    def test_generate_vumark_instance_returns_png_bytes() -> None:
        """``AsyncVuMarkService`` returns VuMark image bytes."""
        vumark_target = VuMarkTarget(name="test-target")
        database = VuMarkDatabase(vumark_targets={vumark_target})

        async def run_test() -> bytes:
            """Generate a VuMark instance image and return its bytes."""
            async with AsyncVuMarkService(
                server_access_key=database.server_access_key,
                server_secret_key=database.server_secret_key,
            ) as client:
                return await client.generate_vumark_instance(
                    target_id=vumark_target.target_id,
                    instance_id=uuid.uuid4().hex,
                    accept=VuMarkAccept.PNG,
                )

        with MockVWS() as mock:
            mock.add_vumark_database(vumark_database=database)
            response_content = asyncio.run(run_test())

        assert response_content.startswith(b"\x89PNG")
