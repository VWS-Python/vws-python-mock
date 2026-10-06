"""Tests for query through the `respx` mock."""

import io

from vws import VWS, CloudRecoService
from vws.transports import HTTPXTransport

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
