"""Tests for the mock of the target list endpoint."""

import io
import os
import uuid
from http import HTTPMethod, HTTPStatus

import pytest
import requests
from vws import VWS
from vws.response import Response
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws._constants import ResultCodes
from mock_vws.database import CloudDatabase
from mock_vws.request_rate_limits import DOCUMENTED_REQUEST_RATE_LIMITS
from tests.mock_vws.fixtures.vuforia_backends import (
    VuforiaBackend,
    running_in_memory_mock,
)
from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.assertions import assert_vws_too_many_requests


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestTargetList:
    """Tests for the mock of the target list endpoint at `/targets`."""

    @staticmethod
    def test_includes_targets(
        *,
        vws_client: VWS,
        unprocessed_target_id: str,
    ) -> None:
        """Targets in the database are returned in the list."""
        assert vws_client.list_targets() == [unprocessed_target_id]

    @staticmethod
    def test_deleted(
        *,
        vws_client: VWS,
        target_id: str,
    ) -> None:
        """Deleted targets are not returned in the list."""
        vws_client.delete_target(target_id=target_id)
        assert not bool(vws_client.list_targets())

    @staticmethod
    def test_order_is_upload_date_then_target_id(
        *,
        verify_mock_vuforia: VuforiaBackend,
        high_quality_image: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """The mock returns targets ordered by upload date.

        The real Vuforia Web Services do not document an order, so we do
        not verify this against them.
        """
        if verify_mock_vuforia == VuforiaBackend.REAL:
            pytest.skip(reason="The real Vuforia does not document an order.")

        target_ids = [
            vws_client.add_target(
                name=uuid.uuid4().hex,
                width=1,
                image=high_quality_image,
                active_flag=True,
                application_metadata=None,
            )
            for _ in range(3)
        ]

        assert vws_client.list_targets() == target_ids


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestInactiveProject:
    """Tests for inactive projects."""

    @staticmethod
    def test_inactive_project(inactive_vws_client: VWS) -> None:
        """The project's active state does not affect the target list."""
        # No exception is raised.
        _ = inactive_vws_client.list_targets()


@pytest.fixture(name="rate_limited_database")
def fixture_rate_limited_database(
    verify_mock_vuforia: VuforiaBackend,
    vuforia_database: CloudDatabase,
) -> CloudDatabase:
    """Return a database which applies real Vuforia's request rate limits.

    The real database applies them itself. Each mock is given a fresh
    database with the limits, so that the shared database which the other
    tests use is not limited.
    """
    if verify_mock_vuforia == VuforiaBackend.REAL:
        return vuforia_database

    database = CloudDatabase(
        request_rate_limits=DOCUMENTED_REQUEST_RATE_LIMITS
    )
    if verify_mock_vuforia == VuforiaBackend.MOCK:
        running_in_memory_mock().add_cloud_database(cloud_database=database)
        return database

    target_manager_base_url = os.environ["TARGET_MANAGER_BASE_URL"]
    response = requests.post(
        url=f"{target_manager_base_url}/cloud_databases",
        json=database.to_dict(),
        timeout=30,
    )
    response.raise_for_status()
    return database


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestRateLimit:
    """Tests for the request rate limit of the target list endpoint."""

    @staticmethod
    def test_two_requests_per_minute(
        *,
        verify_mock_vuforia: VuforiaBackend,
        rate_limited_database: CloudDatabase,
    ) -> None:
        """A third ``GET /targets`` request within a minute is rate
        limited,
        with the empty response which Envoy gives.

        Real Vuforia's window is a fixed clock minute, and the fixture which
        empties the database before each test has already listed the
        targets, so the real backend may reject the first, second or third
        request. The mocks use a rolling window on a fresh database, so they
        reject exactly the third.
        """
        limit = DOCUMENTED_REQUEST_RATE_LIMITS.list_targets
        assert limit is not None
        responses: list[Response] = []
        # Real Vuforia's fixed window means the rejection may come on any
        # of the first three requests, so requests are sent until one is
        # rejected, with a cap well above the limit.
        while True:
            date = rfc_1123_date()
            authorization = authorization_header(
                access_key=rate_limited_database.server_access_key,
                secret_key=rate_limited_database.server_secret_key,
                method=HTTPMethod.GET,
                content=b"",
                content_type="",
                date=date,
                request_path="/targets",
            )
            endpoint = Endpoint(
                base_url="https://vws.vuforia.com",
                path_url="/targets",
                method=HTTPMethod.GET,
                headers={"Authorization": authorization, "Date": date},
                data=b"",
                successful_headers_result_code=ResultCodes.SUCCESS,
                successful_headers_status_code=HTTPStatus.OK,
                access_key=rate_limited_database.server_access_key,
                secret_key=rate_limited_database.server_secret_key,
            )
            response = endpoint.send()
            responses.append(response)
            if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
                break
            assert len(responses) <= limit.max_requests + 2

        status_codes = [response.status_code for response in responses]
        if verify_mock_vuforia != VuforiaBackend.REAL:
            assert status_codes == [
                *[HTTPStatus.OK] * limit.max_requests,
                HTTPStatus.TOO_MANY_REQUESTS,
            ]
        assert status_codes[-1] == HTTPStatus.TOO_MANY_REQUESTS
        assert status_codes.count(HTTPStatus.OK) <= limit.max_requests
        assert_vws_too_many_requests(response=responses[-1])
