"""Tests for ``MockVWS`` intercepting ``httpx`` via synchronous ``vws``
clients.
"""

import io
import uuid

import httpx
import pytest
from vws import VWS, CloudRecoService, VuMarkService
from vws.exceptions.vws_exceptions import UnknownTargetError
from vws.reports import TargetStatuses
from vws.transports import HTTPXTransport
from vws.vumark_accept import VuMarkAccept

from mock_vws import MockVWS
from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.image_matchers import ExactMatcher
from mock_vws.target import VuMarkTarget


class TestVWS:
    """Synchronous ``vws-python`` client usage through the mock via
    ``httpx``.
    """

    @staticmethod
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
                client.get_database_summary_report()

        assert calls == [0.1]

    @staticmethod
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

    @staticmethod
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
                client.get_target_record(target_id=target_id)


class TestCloudRecoService:
    """Synchronous cloud query usage through the mock via ``httpx``."""

    @staticmethod
    def test_query_returns_match(high_quality_image: io.BytesIO) -> None:
        """``CloudRecoService`` returns a match via the mock."""
        database = CloudDatabase()

        with MockVWS(
            processing_time_seconds=0,
            query_match_checker=ExactMatcher(),
        ) as mock:
            mock.add_cloud_database(cloud_database=database)
            vws_client = VWS(
                server_access_key=database.server_access_key,
                server_secret_key=database.server_secret_key,
                transport=HTTPXTransport(),
            )
            query_client = CloudRecoService(
                client_access_key=database.client_access_key,
                client_secret_key=database.client_secret_key,
                transport=HTTPXTransport(),
            )
            target_id = vws_client.add_target(
                name="query-target",
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            vws_client.wait_for_target_processed(target_id=target_id)
            results = query_client.query(image=high_quality_image)
            assert [result.target_id for result in results] == [target_id]


class TestVuMarkService:
    """Synchronous VuMark generation usage through the mock via
    ``httpx``.
    """

    @staticmethod
    def test_generate_vumark_instance_returns_png_bytes() -> None:
        """``VuMarkService`` returns VuMark image bytes."""
        vumark_target = VuMarkTarget(name="test-target")
        database = VuMarkDatabase(vumark_targets={vumark_target})

        with MockVWS() as mock:
            mock.add_vumark_database(vumark_database=database)
            client = VuMarkService(
                server_access_key=database.server_access_key,
                server_secret_key=database.server_secret_key,
                transport=HTTPXTransport(),
            )
            response_content = client.generate_vumark_instance(
                target_id=vumark_target.target_id,
                instance_id=uuid.uuid4().hex,
                accept=VuMarkAccept.PNG,
            )

        assert response_content.startswith(b"\x89PNG")
