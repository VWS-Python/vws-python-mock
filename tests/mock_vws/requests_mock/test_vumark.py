"""Tests for VuMark generation with serialized target timestamps."""

import pytest
from freezegun import freeze_time
from vws import VuMarkService
from vws.transports import HTTPX2Transport, HTTPXTransport, RequestsTransport
from vws.vumark_accept import VuMarkAccept

from mock_vws import MockVWS
from mock_vws.database import VuMarkDatabase
from mock_vws.target import VuMarkTarget


@pytest.mark.parametrize(
    argnames="transport_class",
    argvalues=[RequestsTransport, HTTPXTransport, HTTPX2Transport],
    ids=["requests", "httpx", "httpx2"],
)
@pytest.mark.parametrize(
    argnames="server_time",
    argvalues=["2026-10-08 12:00:00", "2026-10-08 12:00:00.500000"],
    ids=["behind", "equal"],
)
def test_zero_processing_target_generates_instance(
    *,
    transport_class: type[
        RequestsTransport | HTTPXTransport | HTTPX2Transport
    ],
    server_time: str,
) -> None:
    """Zero-duration targets generate even when timestamps are ahead."""
    with freeze_time(time_to_freeze="2026-10-08 12:00:00.500000"):
        target_dict = VuMarkTarget(name="example").to_dict()

    with freeze_time(time_to_freeze=server_time):
        target = VuMarkTarget.from_dict(target_dict=target_dict)
        database = VuMarkDatabase(vumark_targets={target})
        client = VuMarkService(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
            transport=transport_class(),
        )
        with MockVWS() as mock:
            mock.add_vumark_database(vumark_database=database)
            image = client.generate_vumark_instance(
                target_id=target.target_id,
                instance_id="example-instance",
                accept=VuMarkAccept.PNG,
            )

    assert image.startswith(b"\x89PNG\r\n\x1a\n")
