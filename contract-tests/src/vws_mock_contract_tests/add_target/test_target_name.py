"""Tests for the target name field."""

import base64
import io
from http import HTTPStatus

import pytest
from vws import VWS
from vws.exceptions.custom_exceptions import (
    ServerError,
)
from vws.exceptions.vws_exceptions import (
    FailError,
    TargetNameExistError,
)

from vws_mock_contract_tests.add_target.helpers import (
    add_target_to_vws,
)
from vws_mock_contract_tests.utils.assertions import (
    assert_vws_failure,
)

_MAX_CHAR_VALUE = 65535
_MAX_NAME_LENGTH = 64


@pytest.mark.parametrize(
    argnames="name",
    argvalues=[
        "á",
        # We test just below the max character value.
        # This is because targets with the max character value in their
        # names get stuck in the processing stage.
        chr(_MAX_CHAR_VALUE - 2),
        "a" * _MAX_NAME_LENGTH,
    ],
    ids=["Short name", "Max char value", "Long name"],
)
def test_name_valid(
    *,
    name: str,
    image_file_failed_state: io.BytesIO,
    vws_client: VWS,
) -> None:
    """Names between 1 and 64 characters in length are valid."""
    _ = vws_client.add_target(
        name=name,
        width=1,
        image=image_file_failed_state,
        application_metadata=None,
        active_flag=True,
    )


@pytest.mark.parametrize(
    argnames=("name", "status_code"),
    argvalues=[
        (1, HTTPStatus.BAD_REQUEST),
        ("", HTTPStatus.BAD_REQUEST),
        ("a" * (_MAX_NAME_LENGTH + 1), HTTPStatus.BAD_REQUEST),
        (None, HTTPStatus.BAD_REQUEST),
        (chr(_MAX_CHAR_VALUE + 1), HTTPStatus.INTERNAL_SERVER_ERROR),
        (
            chr(_MAX_CHAR_VALUE + 1) * (_MAX_NAME_LENGTH + 1),
            HTTPStatus.BAD_REQUEST,
        ),
    ],
    ids=[
        "Wrong Type",
        "Empty",
        "Too Long",
        "None",
        "Bad char",
        "Bad char too long",
    ],
)
def test_name_invalid(
    *,
    name: str | int | None,
    image_file_failed_state: io.BytesIO,
    status_code: int,
    vws_client: VWS,
) -> None:
    """
    A target's name must be a string of length 0 < N < 65, with
    characters
    in a particular range.
    """
    image_data = image_file_failed_state.getvalue()
    image_data_encoded = base64.b64encode(s=image_data).decode(
        encoding="ascii",
    )
    data = {
        "name": name,
        "width": 1,
        "image": image_data_encoded,
        "application_metadata": None,
        "active_flag": True,
    }

    exc: pytest.ExceptionInfo[FailError | ServerError]

    if status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
        with pytest.raises(expected_exception=ServerError) as exc:
            _ = add_target_to_vws(
                vws_client=vws_client,
                data=data,
                content_type="application/json",
            )
    else:
        with pytest.raises(expected_exception=FailError) as exc:
            _ = add_target_to_vws(
                vws_client=vws_client,
                data=data,
                content_type="application/json",
            )

    assert_vws_failure(
        response=exc.value.response,
        status_code=status_code,
        result_code="Fail",
    )


def test_existing_target_name(
    *,
    image_file_failed_state: io.BytesIO,
    vws_client: VWS,
) -> None:
    """Only one target can have a given name."""
    _ = vws_client.add_target(
        name="example_name",
        width=1,
        image=image_file_failed_state,
        application_metadata=None,
        active_flag=True,
    )

    with pytest.raises(expected_exception=TargetNameExistError) as exc:
        _ = vws_client.add_target(
            name="example_name",
            width=1,
            image=image_file_failed_state,
            application_metadata=None,
            active_flag=True,
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.FORBIDDEN,
        result_code="TargetNameExist",
    )


def test_deleted_existing_target_name(
    *,
    image_file_failed_state: io.BytesIO,
    vws_client: VWS,
) -> None:
    """A target can be added with the name of a deleted target."""
    target_id = vws_client.add_target(
        name="example_name",
        width=1,
        image=image_file_failed_state,
        application_metadata=None,
        active_flag=True,
    )

    vws_client.wait_for_target_processed(target_id=target_id)
    vws_client.delete_target(target_id=target_id)
    _ = vws_client.add_target(
        name="example_name",
        width=1,
        image=image_file_failed_state,
        application_metadata=None,
        active_flag=True,
    )
