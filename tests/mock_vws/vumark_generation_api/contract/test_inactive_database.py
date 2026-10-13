"""Tests for VuMark generation with an inactive database."""

from http import HTTPStatus
from uuid import uuid4

from mock_vws._constants import ResultCodes
from tests.mock_vws.fixtures.credentials import (
    InactiveVuMarkCloudDatabase,
)
from tests.mock_vws.vumark_generation_api.helpers import (
    make_vumark_request,
)


def test_inactive_database(
    inactive_vumark_database: InactiveVuMarkCloudDatabase,
) -> None:
    """Calling the VuMark generation API with credentials for an
    inactive database returns ProjectInactive.
    """
    response = make_vumark_request(
        server_access_key=inactive_vumark_database.server_access_key,
        server_secret_key=inactive_vumark_database.server_secret_key,
        target_id=uuid4().hex,
        instance_id=uuid4().hex,
        accept="image/png",
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    response_json = response.json()
    assert response_json["result_code"] == ResultCodes.UNKNOWN_TARGET.value
