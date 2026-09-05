"""Tests for ``MockVWS`` intercepting ``httpx2`` via ``vws`` clients."""

import asyncio
import io
import socket
import uuid
from collections.abc import Coroutine
from http import HTTPStatus
from typing import Any

import httpx2
import pytest
from vws import (
    VWS,
    AsyncCloudRecoService,
    AsyncVuMarkService,
    AsyncVWS,
    CloudRecoService,
    VuMarkService,
)
from vws.exceptions.vws_exceptions import (
    AuthenticationFailureError,
    UnknownTargetError,
)
from vws.reports import TargetStatuses
from vws.vumark_accept import VuMarkAccept

from mock_vws import MockVWS
from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.image_matchers import ExactMatcher
from mock_vws.target import VuMarkTarget
from tests.mock_vws.utils.httpx2_transports import (
    AsyncHTTPX2Transport,
    HTTPX2Transport,
)
from tests.mock_vws.verification import UnverifiedReason, mock_only

pytestmark = mock_only(
    reason=UnverifiedReason.NO_VUFORIA_CLAIM,
    detail=(
        "These exercise the mock's interception of ``httpx2``. The Vuforia "
        "behavior which the mock then shows is verified by the tests which "
        "run against every backend."
    ),
)

_MODEL_TARGET_AUTHORIZATION = (
    "Bearer eyJhbGciOiJtb2NrIn0."
    "eyJzY29wZSI6Im1vZGVsdGFyZ2V0cy5zdGFuZGFyZG1vZGVsdGFyZ2V0LmFsbCJ9."
    "c2lnbmF0dXJl"
)
_MODEL_TARGET_DATASET_REQUEST = {
    "name": "dataset-name",
    "targetSdk": "10.18",
    "models": [
        {
            "name": "model-name",
            "cadDataUrl": "https://example.com/model.glb",
            "views": [
                {
                    "name": "view-name",
                    "guideViewPosition": {
                        "translation": [0, 0, 5],
                        "rotation": [0, 0, 0, 1],
                    },
                },
            ],
        },
    ],
}


def _run[T](*, coroutine: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine to completion.

    The test suite has no plugin for asynchronous tests, so asynchronous
    clients are driven from synchronous tests with this.

    Args:
        coroutine: The coroutine to run.

    Returns:
        The result of the given coroutine.
    """
    return asyncio.run(main=coroutine)


def _unused_local_url() -> str:
    """A URL of a local port which nothing is listening on.

    Returns:
        The URL of a port which was free when this was called.
    """
    sock = socket.socket()
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://localhost:{port}"


async def _async_get(*, url: str) -> httpx2.Response:
    """Make an asynchronous ``httpx2`` request.

    Args:
        url: The URL to request.

    Returns:
        The response to the request.
    """
    async with httpx2.AsyncClient() as client:
        return await client.get(url=url, timeout=30)


class TestVWS:
    """Synchronous ``vws-python`` client usage through the mock via
    ``httpx2``.
    """

    @staticmethod
    def test_response_delay_causes_httpx2_timeout() -> None:
        """``httpx2`` timeouts are surfaced through ``VWS``."""
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
                # A ``(connect, read)`` tuple, so that the read timeout
                # is the one which the response delay exceeds.
                request_timeout_seconds=(30.0, 0.1),
                transport=HTTPX2Transport(),
            )
            with pytest.raises(expected_exception=httpx2.ReadTimeout):
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
                transport=HTTPX2Transport(),
            )
            report = client.get_database_summary_report()
            database_name = report.name

        assert database_name == database.database_name

    @staticmethod
    def test_bad_credentials_are_rejected() -> None:
        """Requests which are signed with the wrong keys are rejected."""
        database = CloudDatabase()

        with MockVWS() as mock:
            mock.add_cloud_database(cloud_database=database)
            client = VWS(
                server_access_key=database.server_access_key,
                server_secret_key="wrong-secret-key",
                transport=HTTPX2Transport(),
            )
            with pytest.raises(
                expected_exception=AuthenticationFailureError,
            ):
                client.get_database_summary_report()

    @staticmethod
    def test_add_get_and_delete_target(
        image_file_success_state_low_rating: io.BytesIO,
    ) -> None:
        """A target life cycle works through ``VWS``."""
        database = CloudDatabase()
        target_name = "httpx2-target"

        with MockVWS(processing_time_seconds=0) as mock:
            mock.add_cloud_database(cloud_database=database)
            client = VWS(
                server_access_key=database.server_access_key,
                server_secret_key=database.server_secret_key,
                transport=HTTPX2Transport(),
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

    @staticmethod
    def test_nested_mocks() -> None:
        """A mock inside another mock leaves the outer one working.

        The innermost mock is the only one which answers while it is
        running, which is what the ``requests`` backend does too, and the
        outer mock answers again once the inner one has stopped.
        """
        outer_url = "https://vws.vuforia.com/summary"
        inner_url = "https://vuforia.vws.example.com/summary"

        with MockVWS():
            with MockVWS(base_vws_url="https://vuforia.vws.example.com"):
                inner_response = httpx2.get(url=inner_url, timeout=30)
                with pytest.raises(expected_exception=httpx2.ConnectError):
                    httpx2.get(url=outer_url, timeout=30)
            outer_response = httpx2.get(url=outer_url, timeout=30)

            with pytest.raises(expected_exception=httpx2.ConnectError):
                httpx2.get(url=inner_url, timeout=30)

        assert inner_response.status_code == HTTPStatus.UNAUTHORIZED
        assert outer_response.status_code == HTTPStatus.UNAUTHORIZED


class TestAsyncVWS:
    """Asynchronous ``vws-python`` client usage through the mock via
    ``httpx2``.
    """

    @staticmethod
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
                _run(coroutine=get_summary())

        assert calls == [0.1]

    @staticmethod
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
            name = _run(coroutine=life_cycle())

        assert name == target_name


class TestCloudRecoService:
    """Cloud query usage through the mock via ``httpx2``."""

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
                transport=HTTPX2Transport(),
            )
            query_client = CloudRecoService(
                client_access_key=database.client_access_key,
                client_secret_key=database.client_secret_key,
                transport=HTTPX2Transport(),
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

    @staticmethod
    def test_async_query_returns_match(
        high_quality_image: io.BytesIO,
    ) -> None:
        """``AsyncCloudRecoService`` returns a match via the mock."""
        database = CloudDatabase()

        async def query() -> list[str]:
            """Query for an image.

            Returns:
                The IDs of the targets which the query matched.
            """
            query_client = AsyncCloudRecoService(
                client_access_key=database.client_access_key,
                client_secret_key=database.client_secret_key,
                transport=AsyncHTTPX2Transport(),
            )
            try:
                results = await query_client.query(image=high_quality_image)
            finally:
                await query_client.aclose()
            return [result.target_id for result in results]

        with MockVWS(
            processing_time_seconds=0,
            query_match_checker=ExactMatcher(),
        ) as mock:
            mock.add_cloud_database(cloud_database=database)
            vws_client = VWS(
                server_access_key=database.server_access_key,
                server_secret_key=database.server_secret_key,
                transport=HTTPX2Transport(),
            )
            added_target_id = vws_client.add_target(
                name="query-target",
                width=1,
                image=high_quality_image,
                application_metadata=None,
                active_flag=True,
            )
            vws_client.wait_for_target_processed(target_id=added_target_id)
            matched = _run(coroutine=query())

        assert matched == [added_target_id]


class TestVuMarkService:
    """VuMark generation usage through the mock via ``httpx2``."""

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
                transport=HTTPX2Transport(),
            )
            response_content = client.generate_vumark_instance(
                target_id=vumark_target.target_id,
                instance_id=uuid.uuid4().hex,
                accept=VuMarkAccept.PNG,
            )

        assert response_content.startswith(b"\x89PNG")

    @staticmethod
    def test_async_generate_vumark_instance_returns_png_bytes() -> None:
        """``AsyncVuMarkService`` returns VuMark image bytes."""
        vumark_target = VuMarkTarget(name="test-target")
        database = VuMarkDatabase(vumark_targets={vumark_target})

        async def generate() -> bytes:
            """Generate a VuMark instance.

            Returns:
                The bytes of the generated VuMark image.
            """
            client = AsyncVuMarkService(
                server_access_key=database.server_access_key,
                server_secret_key=database.server_secret_key,
                transport=AsyncHTTPX2Transport(),
            )
            try:
                return await client.generate_vumark_instance(
                    target_id=vumark_target.target_id,
                    instance_id=uuid.uuid4().hex,
                    accept=VuMarkAccept.PNG,
                )
            finally:
                await client.aclose()

        with MockVWS() as mock:
            mock.add_vumark_database(vumark_database=database)
            response_content = _run(coroutine=generate())

        assert response_content.startswith(b"\x89PNG")


class TestTransportClose:
    """Closing a transport closes the ``httpx2`` client underneath it."""

    @staticmethod
    def test_close() -> None:
        """A closed ``HTTPX2Transport`` cannot make a request."""
        transport = HTTPX2Transport()
        transport.close()

        with MockVWS(), pytest.raises(expected_exception=RuntimeError):
            transport(
                method="GET",
                url="https://vws.vuforia.com/summary",
                headers={},
                data=b"",
                request_timeout=30.0,
            )

    @staticmethod
    def test_aclose() -> None:
        """A closed ``AsyncHTTPX2Transport`` cannot make a request."""

        async def close_then_request() -> None:
            """Close the transport and then try to use it."""
            transport = AsyncHTTPX2Transport()
            await transport.aclose()
            await transport(
                method="GET",
                url="https://vws.vuforia.com/summary",
                headers={},
                data=b"",
                request_timeout=30.0,
            )

        with MockVWS(), pytest.raises(expected_exception=RuntimeError):
            _run(coroutine=close_then_request())


class TestAsyncInterception:
    """Which addresses an asynchronous ``httpx2`` client can reach."""

    @staticmethod
    def test_unmocked_address_blocked() -> None:
        """Requests to non-Vuforia addresses are blocked."""
        url = _unused_local_url()

        with (
            MockVWS(),
            pytest.raises(expected_exception=httpx2.ConnectError),
        ):
            _run(coroutine=_async_get(url=url))

    @staticmethod
    def test_real_http() -> None:
        """With ``real_http``, requests reach the transport underneath.

        Nothing is listening on the address, so the error comes from that
        transport rather than from the mock.
        """
        url = _unused_local_url()

        with (
            MockVWS(real_http=True),
            pytest.raises(expected_exception=httpx2.ConnectError),
        ):
            _run(coroutine=_async_get(url=url))


class TestModelTargetWebAPI:
    """Model Target Web API usage through the mock via ``httpx2``."""

    @staticmethod
    def test_standard_dataset_status() -> None:
        """``httpx2`` requests can use Model Target Web API routes."""
        with MockVWS(processing_time_seconds=0):
            create_response = httpx2.post(
                url="https://vws.vuforia.com/modeltargets/datasets",
                headers={"Authorization": _MODEL_TARGET_AUTHORIZATION},
                json=_MODEL_TARGET_DATASET_REQUEST,
                timeout=30,
            )
            dataset_uuid = create_response.json()["uuid"]
            status_response = httpx2.get(
                url=(
                    "https://vws.vuforia.com/modeltargets/datasets/"
                    f"{dataset_uuid}/status"
                ),
                headers={"Authorization": _MODEL_TARGET_AUTHORIZATION},
                timeout=30,
            )

        assert create_response.status_code == HTTPStatus.CREATED
        assert status_response.json()["status"] == "done"
