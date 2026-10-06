"""Tests for VuMark through the `respx` mock."""

import uuid

from vws import VuMarkService
from vws.transports import HTTPXTransport
from vws.vumark_accept import VuMarkAccept

from mock_vws import MockVWS
from mock_vws.database import VuMarkDatabase
from mock_vws.target import VuMarkTarget


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
