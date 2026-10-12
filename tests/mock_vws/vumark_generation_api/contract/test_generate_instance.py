"""Tests for the VuMark instance generation endpoint."""

import json
from http import HTTPStatus
from uuid import uuid4

import pytest
from vws import VWS
from vws.exceptions.vws_exceptions import (
    InvalidInstanceIdError,
    InvalidTargetTypeError,
)
from vws.vumark_accept import VuMarkAccept

from mock_vws._constants import ResultCodes
from mock_vws.database import CloudDatabase
from tests.mock_vws.fixtures.credentials import (
    VuMarkCloudDatabase,
)
from tests.mock_vws.utils import make_image_file
from tests.mock_vws.vumark_generation_api.helpers import (
    PDF_SIGNATURE,
    PNG_SIGNATURE,
    SVG_START,
    JsonValue,
    make_vumark_request,
    make_vumark_service,
)


@pytest.mark.parametrize(
    argnames=("accept", "expected_signature"),
    argvalues=[
        pytest.param(VuMarkAccept.PNG, PNG_SIGNATURE, id="png"),
        pytest.param(
            VuMarkAccept.SVG,
            SVG_START,
            id="svg",
        ),
        pytest.param(
            VuMarkAccept.PDF,
            PDF_SIGNATURE,
            id="pdf",
        ),
    ],
)
def test_generate_instance_format(
    *,
    accept: VuMarkAccept,
    expected_signature: bytes,
    vumark_vuforia_database: VuMarkCloudDatabase,
) -> None:
    """A VuMark instance can be generated in the requested format."""
    vumark_client = make_vumark_service(
        server_access_key=vumark_vuforia_database.server_access_key,
        server_secret_key=vumark_vuforia_database.server_secret_key,
    )
    vumark_bytes = vumark_client.generate_vumark_instance(
        target_id=vumark_vuforia_database.target_id,
        instance_id=uuid4().hex,
        accept=accept,
    )

    assert vumark_bytes.strip().startswith(expected_signature)
    assert len(vumark_bytes) > len(expected_signature)


@pytest.mark.parametrize(
    argnames=("accept", "expected_content_type"),
    argvalues=[
        pytest.param("image/png", "image/png", id="png"),
        pytest.param("image/svg+xml", "image/svg+xml", id="svg"),
        pytest.param("application/pdf", "application/pdf", id="pdf"),
    ],
)
def test_generate_instance_content_type_header(
    *,
    accept: str,
    expected_content_type: str,
    vumark_vuforia_database: VuMarkCloudDatabase,
) -> None:
    """VuMark image responses include the expected content type."""
    response = make_vumark_request(
        server_access_key=vumark_vuforia_database.server_access_key,
        server_secret_key=vumark_vuforia_database.server_secret_key,
        target_id=vumark_vuforia_database.target_id,
        instance_id=uuid4().hex,
        accept=accept,
    )

    assert response.status_code == HTTPStatus.OK
    assert (
        response.headers["Content-Type"].split(sep=";")[0]
        == expected_content_type
    )


def test_invalid_accept_header(
    vumark_vuforia_database: VuMarkCloudDatabase,
) -> None:
    """An unsupported Accept header returns an error."""
    response = make_vumark_request(
        server_access_key=vumark_vuforia_database.server_access_key,
        server_secret_key=vumark_vuforia_database.server_secret_key,
        target_id=vumark_vuforia_database.target_id,
        instance_id=uuid4().hex,
        accept="text/plain",
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    response_json = response.json()
    assert (
        response_json["result_code"] == ResultCodes.INVALID_ACCEPT_HEADER.value
    )


def test_empty_instance_id(
    vumark_vuforia_database: VuMarkCloudDatabase,
) -> None:
    """An empty instance_id returns InvalidInstanceId."""
    vumark_client = make_vumark_service(
        server_access_key=vumark_vuforia_database.server_access_key,
        server_secret_key=vumark_vuforia_database.server_secret_key,
    )
    with pytest.raises(expected_exception=InvalidInstanceIdError) as exc:
        _ = vumark_client.generate_vumark_instance(
            target_id=vumark_vuforia_database.target_id,
            instance_id="",
            accept=VuMarkAccept.PNG,
        )

    assert exc.value.response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    response_json = json.loads(s=exc.value.response.text)
    assert (
        response_json["result_code"] == ResultCodes.INVALID_INSTANCE_ID.value
    )


@pytest.mark.parametrize(
    argnames="instance_id",
    argvalues=[
        pytest.param(5, id="int"),
        pytest.param(0, id="zero"),
        pytest.param(0.0, id="zero_float"),
        pytest.param(1.5, id="float"),
        pytest.param(True, id="true"),
        pytest.param(False, id="false"),
        pytest.param([1], id="array"),
        pytest.param([], id="empty_array"),
        pytest.param({"a": 1}, id="object"),
        pytest.param({}, id="empty_object"),
        pytest.param(None, id="null"),
    ],
)
def test_non_string_instance_id(
    *,
    instance_id: JsonValue,
    vumark_vuforia_database: VuMarkCloudDatabase,
) -> None:
    """An instance_id which is not a string returns BadRequest."""
    response = make_vumark_request(
        server_access_key=vumark_vuforia_database.server_access_key,
        server_secret_key=vumark_vuforia_database.server_secret_key,
        target_id=vumark_vuforia_database.target_id,
        instance_id=instance_id,
        accept="image/png",
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    response_json = response.json()
    assert response_json["result_code"] == ResultCodes.BAD_REQUEST.value


def test_unknown_target(
    vumark_vuforia_database: VuMarkCloudDatabase,
) -> None:
    """An unknown target_id returns UnknownTarget."""
    response = make_vumark_request(
        server_access_key=vumark_vuforia_database.server_access_key,
        server_secret_key=vumark_vuforia_database.server_secret_key,
        target_id=uuid4().hex,
        instance_id=uuid4().hex,
        accept=VuMarkAccept.PNG,
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    response_json = response.json()
    assert response_json["result_code"] == ResultCodes.UNKNOWN_TARGET.value


def test_non_vumark_database(
    vuforia_database: CloudDatabase,
) -> None:
    """Generating a VuMark instance for a target in a non-VuMark
    database returns InvalidTargetType.
    """
    server_access_key = vuforia_database.server_access_key
    server_secret_key = vuforia_database.server_secret_key
    vws_client = VWS(
        server_access_key=server_access_key,
        server_secret_key=server_secret_key,
    )
    vumark_client = make_vumark_service(
        server_access_key=server_access_key,
        server_secret_key=server_secret_key,
    )
    image = make_image_file(
        file_format="PNG",
        color_space="RGB",
        width=8,
        height=8,
    )
    target_id = vws_client.add_target(
        name="test",
        width=1,
        image=image,
        active_flag=True,
        application_metadata=None,
    )
    with pytest.raises(expected_exception=InvalidTargetTypeError) as exc:
        _ = vumark_client.generate_vumark_instance(
            target_id=target_id,
            instance_id=uuid4().hex,
            accept=VuMarkAccept.PNG,
        )

    assert exc.value.response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    response_json = json.loads(s=exc.value.response.text)
    assert (
        response_json["result_code"] == ResultCodes.INVALID_TARGET_TYPE.value
    )


def test_successful_target(
    vumark_vuforia_database: VuMarkCloudDatabase,
) -> None:
    """A VuMark target that has finished processing succeeds."""
    vumark_client = make_vumark_service(
        server_access_key=vumark_vuforia_database.server_access_key,
        server_secret_key=vumark_vuforia_database.server_secret_key,
    )
    vumark_bytes = vumark_client.generate_vumark_instance(
        target_id=vumark_vuforia_database.target_id,
        instance_id=uuid4().hex,
        accept=VuMarkAccept.PNG,
    )

    assert vumark_bytes.strip().startswith(PNG_SIGNATURE)
