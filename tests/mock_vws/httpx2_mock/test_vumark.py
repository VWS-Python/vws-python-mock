"""Tests for VuMark through the `httpx2` mock.

VuMark generation usage through the mock via ``httpx2``.
"""

import uuid

from vws import (
    AsyncVuMarkService,
    VuMarkService,
)
from vws.transports import AsyncHTTPX2Transport, HTTPX2Transport
from vws.vumark_accept import VuMarkAccept

from mock_vws import MockVWS
from mock_vws.database import VuMarkDatabase
from mock_vws.target import VuMarkTarget
from tests.mock_vws.httpx2_mock.helpers import run


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
        response_content = run(coroutine=generate())

    assert response_content.startswith(b"\x89PNG")
