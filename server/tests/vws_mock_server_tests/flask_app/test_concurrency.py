"""Concurrent VuMark target-manager operations."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus

from pydantic import TypeAdapter

from mock_vws.database import VuMarkDatabase, VuMarkDatabaseDict
from mock_vws.target import VuMarkTarget
from vws_mock_server.target_manager import TARGET_MANAGER_FLASK_APP

_NUM_TARGETS = 64


def test_create_targets_while_listing_databases() -> None:
    """VuMark writes and listings can share the target manager safely."""
    database = VuMarkDatabase()
    with TARGET_MANAGER_FLASK_APP.test_client() as client:
        response = client.post("/vumark_databases", json=database.to_dict())
        assert response.status_code == HTTPStatus.CREATED

    def create_and_list(_: int) -> None:
        """Create one template while reading the shared database set."""
        target = VuMarkTarget(name=uuid.uuid4().hex)
        with TARGET_MANAGER_FLASK_APP.test_client() as client:
            response = client.post(
                f"/vumark_databases/{database.database_name}/vumark_targets",
                json=target.to_dict(),
            )
            assert response.status_code == HTTPStatus.CREATED
            response = client.get("/vumark_databases")
            assert response.status_code == HTTPStatus.OK

    with ThreadPoolExecutor(max_workers=8) as pool:
        _ = list(pool.map(create_and_list, range(_NUM_TARGETS)))

    with TARGET_MANAGER_FLASK_APP.test_client() as client:
        response = client.get("/vumark_databases")
        body = TypeAdapter(type=list[VuMarkDatabaseDict]).validate_json(
            response.data
        )
        assert len(body) == 1
        assert len(list(body[0]["vumark_targets"])) == _NUM_TARGETS
