"""Tests for the target name field."""

import io
from http import HTTPStatus

import pytest
from vws import VWS
from vws.exceptions.base_exceptions import VWSError
from vws.exceptions.vws_exceptions import (
    TargetNameExistError,
)

from vws_mock_contract_tests.update_target.helpers import (
    update_target,
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
    target_id: str,
    vws_client: VWS,
) -> None:
    """A target's name must be a string of length 0 < N < 65.

    We test characters out of range in another test as that gives a
    different error.
    """
    vws_client.update_target(target_id=target_id, name=name)
    target_details = vws_client.get_target_record(target_id=target_id)
    assert target_details.target_record.name == name


@pytest.mark.parametrize(
    argnames=("name", "status_code", "result_code"),
    argvalues=[
        (1, HTTPStatus.BAD_REQUEST, "Fail"),
        ("", HTTPStatus.BAD_REQUEST, "Fail"),
        (
            "a" * (_MAX_NAME_LENGTH + 1),
            HTTPStatus.BAD_REQUEST,
            "Fail",
        ),
        (None, HTTPStatus.BAD_REQUEST, "Fail"),
        (
            chr(_MAX_CHAR_VALUE + 1),
            HTTPStatus.FORBIDDEN,
            "TargetNameExist",
        ),
        (
            chr(_MAX_CHAR_VALUE + 1) * (_MAX_NAME_LENGTH + 1),
            HTTPStatus.BAD_REQUEST,
            "Fail",
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
    target_id: str,
    vws_client: VWS,
    status_code: int,
    result_code: str,
) -> None:
    """A target's name must be a string of length 0 < N < 65."""
    with pytest.raises(expected_exception=VWSError) as exc:
        _ = update_target(
            vws_client=vws_client,
            data={"name": name},
            target_id=target_id,
            content_type="application/json",
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=status_code,
        result_code=result_code,
    )


def test_existing_target_name(
    *,
    image_file_success_state_low_rating: io.BytesIO,
    vws_client: VWS,
) -> None:
    """Only one target can have a given name."""
    first_target_name = "example_name"
    second_target_name = "another_example_name"

    first_target_id = vws_client.add_target(
        name=first_target_name,
        width=1,
        image=image_file_success_state_low_rating,
        active_flag=True,
        application_metadata=None,
    )

    second_target_id = vws_client.add_target(
        name=second_target_name,
        width=1,
        image=image_file_success_state_low_rating,
        active_flag=True,
        application_metadata=None,
    )

    vws_client.wait_for_target_processed(target_id=first_target_id)
    vws_client.wait_for_target_processed(target_id=second_target_id)

    with pytest.raises(expected_exception=TargetNameExistError) as exc:
        vws_client.update_target(
            target_id=second_target_id,
            name=first_target_name,
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.FORBIDDEN,
        result_code="TargetNameExist",
    )


def test_same_name_given(
    *,
    image_file_success_state_low_rating: io.BytesIO,
    vws_client: VWS,
) -> None:
    """Updating a target with its own name does not give an error."""
    name = "example"

    target_id = vws_client.add_target(
        name=name,
        width=1,
        image=image_file_success_state_low_rating,
        active_flag=True,
        application_metadata=None,
    )

    vws_client.wait_for_target_processed(target_id=target_id)
    vws_client.update_target(target_id=target_id, name=name)
    target_details = vws_client.get_target_record(target_id=target_id)
    assert target_details.target_record.name == name
