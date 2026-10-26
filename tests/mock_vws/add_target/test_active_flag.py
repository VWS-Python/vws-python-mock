"""Tests for the active flag parameter."""

import base64
import io
import json
from http import HTTPStatus

import pytest
from vws import VWS
from vws.exceptions.vws_exceptions import (
    FailError,
)

from tests.mock_vws.add_target.helpers import (
    add_target_to_vws,
    assert_success,
)
from tests.mock_vws.utils.assertions import (
    assert_vws_failure,
)


@pytest.mark.parametrize(
    argnames="active_flag",
    argvalues=[True, False, None],
)
def test_valid(
    *,
    active_flag: bool | None,
    image_file_failed_state: io.BytesIO,
    vws_client: VWS,
) -> None:
    """Boolean values and NULL are valid active flags."""
    image_data = image_file_failed_state.getvalue()
    image_data_encoded = base64.b64encode(s=image_data).decode(
        encoding="ascii",
    )
    content_type = "application/json"

    data = {
        "name": "example",
        "width": 1,
        "image": image_data_encoded,
        "active_flag": active_flag,
    }

    response = add_target_to_vws(
        vws_client=vws_client,
        data=data,
        content_type=content_type,
    )

    assert_success(response=response)


def test_invalid(
    *,
    image_file_failed_state: io.BytesIO,
    vws_client: VWS,
) -> None:
    """
    Values which are not Boolean values or NULL are not valid active
    flags.
    """
    active_flag = "string"
    image_data = image_file_failed_state.getvalue()
    image_data_encoded = base64.b64encode(s=image_data).decode(
        encoding="ascii"
    )
    content_type = "application/json"

    data = {
        "name": "example",
        "width": 1,
        "image": image_data_encoded,
        "active_flag": active_flag,
    }

    with pytest.raises(expected_exception=FailError) as exc:
        _ = add_target_to_vws(
            vws_client=vws_client,
            data=data,
            content_type=content_type,
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.BAD_REQUEST,
        result_code="Fail",
    )


def test_not_set(
    *,
    vws_client: VWS,
    image_file_failed_state: io.BytesIO,
) -> None:
    """The active flag defaults to True if it is not set."""
    image_data = image_file_failed_state.getvalue()
    image_data_encoded = base64.b64encode(s=image_data).decode(
        encoding="ascii"
    )

    data = {
        "name": "my_example_name",
        "width": 1234,
        "image": image_data_encoded,
    }

    response = add_target_to_vws(
        vws_client=vws_client, data=data, content_type="application/json"
    )
    response_json = json.loads(s=response.text)
    assert isinstance(response_json, dict)
    assert isinstance(response_json["target_id"], str)
    target_id: str = response_json["target_id"]
    target_details = vws_client.get_target_record(target_id=target_id)
    assert target_details.target_record.active_flag is True


def test_set_to_none(
    *,
    vws_client: VWS,
    image_file_failed_state: io.BytesIO,
) -> None:
    """The active flag defaults to True if it is set to NULL."""
    image_data = image_file_failed_state.getvalue()
    image_data_encoded = base64.b64encode(s=image_data).decode(
        encoding="ascii"
    )

    data = {
        "name": "my_example_name",
        "width": 1234,
        "image": image_data_encoded,
        "active_flag": None,
    }

    response = add_target_to_vws(
        vws_client=vws_client, data=data, content_type="application/json"
    )

    response_json = json.loads(s=response.text)
    assert isinstance(response_json, dict)
    assert isinstance(response_json["target_id"], str)
    target_id: str = response_json["target_id"]
    target_details = vws_client.get_target_record(target_id=target_id)
    assert target_details.target_record.active_flag is True
