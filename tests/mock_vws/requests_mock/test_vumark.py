"""Tests for VuMark generation with serialized target timestamps."""

import json
from http import HTTPStatus

import httpx
import httpx2
import pytest
import requests
from freezegun import freeze_time
from vws import VuMarkService
from vws.exceptions.base_exceptions import VWSError
from vws.transports import HTTPX2Transport, HTTPXTransport, RequestsTransport
from vws.vumark_accept import VuMarkAccept
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws import MockVWS
from mock_vws.database import VuMarkDatabase
from mock_vws.states import States
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


@pytest.mark.parametrize(
    argnames=("state", "result_code"),
    argvalues=[
        (States.PROJECT_SUSPENDED, "ProjectSuspended"),
        (States.PROJECT_HAS_NO_API_ACCESS, "ProjectHasNoApiAccess"),
    ],
)
def test_vumark_database_state(state: States, result_code: str) -> None:
    """Unavailable VuMark databases reject generation before target lookup."""
    database = VuMarkDatabase(state=state)
    with MockVWS() as mock:
        mock.add_vumark_database(vumark_database=database)
        client = VuMarkService(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
        with pytest.raises(expected_exception=VWSError) as error:
            _ = client.generate_vumark_instance(
                target_id="template",
                instance_id="123",
                accept=VuMarkAccept.PNG,
            )
    assert result_code in error.value.response.text


@pytest.mark.parametrize(
    argnames="transport_class",
    argvalues=[RequestsTransport, HTTPXTransport, HTTPX2Transport],
)
def test_vumark_custom_path_prefix(
    transport_class: type[
        RequestsTransport | HTTPXTransport | HTTPX2Transport
    ],
) -> None:
    """Each transport signs and routes VuMark requests under a custom
    prefix.
    """
    target = VuMarkTarget(name="template")
    database = VuMarkDatabase(vumark_targets={target})
    base_url = "https://example.com/prefix"
    with MockVWS(base_vws_url=base_url) as mock:
        mock.add_vumark_database(vumark_database=database)
        client = VuMarkService(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
            base_vws_url=base_url,
            transport=transport_class(),
        )
        result = client.generate_vumark_instance(
            target_id=target.target_id,
            instance_id="123",
            accept=VuMarkAccept.PNG,
        )
    assert result.startswith(b"\x89PNG")


@pytest.mark.parametrize(
    argnames=("transport_class", "error_class"),
    argvalues=[
        (HTTPXTransport, httpx.ReadTimeout),
        (HTTPX2Transport, httpx2.ReadTimeout),
    ],
)
def test_vumark_response_delay_timeout(
    transport_class: type[HTTPXTransport | HTTPX2Transport],
    error_class: type[httpx.ReadTimeout | httpx2.ReadTimeout],
) -> None:
    """A delayed VuMark response raises the transport's native timeout."""
    target = VuMarkTarget(name="template")
    database = VuMarkDatabase(vumark_targets={target})
    sleeps: list[float] = []
    with MockVWS(response_delay_seconds=0.11, sleep_fn=sleeps.append) as mock:
        mock.add_vumark_database(vumark_database=database)
        client = VuMarkService(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
            transport=transport_class(),
            request_timeout_seconds=0.1,
        )
        with pytest.raises(expected_exception=error_class):
            _ = client.generate_vumark_instance(
                target_id=target.target_id,
                instance_id="123",
                accept=VuMarkAccept.PNG,
            )
    assert sleeps == [0.1]


@pytest.mark.parametrize(
    argnames=("content_type", "extra_key", "expected_status"),
    argvalues=[
        ("", False, HTTPStatus.UNAUTHORIZED),
        ("application/json", True, HTTPStatus.BAD_REQUEST),
    ],
)
def test_vumark_request_shape(
    *,
    content_type: str,
    extra_key: bool,
    expected_status: HTTPStatus,
) -> None:
    """VuMark requests require a content type and only the instance
    key.
    """
    target = VuMarkTarget(name="template")
    database = VuMarkDatabase(vumark_targets={target})
    data = {"instance_id": "123"}
    if extra_key:
        data["extra"] = "value"
    body = json.dumps(obj=data).encode()
    path = f"/targets/{target.target_id}/instances"
    date = rfc_1123_date()
    signature = authorization_header(
        access_key=database.server_access_key,
        secret_key=database.server_secret_key,
        method="POST",
        content=body,
        content_type=content_type,
        date=date,
        request_path=path,
    )
    with MockVWS() as mock:
        mock.add_vumark_database(vumark_database=database)
        response = requests.post(
            url="https://vws.vuforia.com" + path,
            data=body,
            headers={
                "Authorization": signature,
                "Date": date,
                "Content-Type": content_type,
            },
            timeout=30,
        )
    assert response.status_code == expected_status
