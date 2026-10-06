"""Tests for query through the `httpx2` mock.

Cloud query usage through the mock via ``httpx2``.
"""

import asyncio
import io

from vws import (
    VWS,
    AsyncCloudRecoService,
    CloudRecoService,
)
from vws.transports import AsyncHTTPX2Transport, HTTPX2Transport

from mock_vws import MockVWS
from mock_vws.database import CloudDatabase
from mock_vws.image_matchers import ExactMatcher


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
        matched = asyncio.run(main=query())

    assert matched == [added_target_id]
