"""Tests for the active flag parameter."""

import io
import uuid
from http import HTTPStatus

import pytest
from vws import VWS
from vws.exceptions.vws_exceptions import (
    FailError,
)

from tests.mock_vws.update_target.helpers import (
    update_target,
)
from tests.mock_vws.utils.assertions import (
    assert_vws_failure,
)


@pytest.mark.parametrize(
    argnames="initial_active_flag",
    argvalues=[True, False],
)
@pytest.mark.parametrize(
    argnames="desired_active_flag",
    argvalues=[True, False],
)
def test_active_flag(
    *,
    vws_client: VWS,
    image_file_success_state_low_rating: io.BytesIO,
    initial_active_flag: bool,
    desired_active_flag: bool,
) -> None:
    """Setting the active flag to a Boolean value changes it."""
    target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=image_file_success_state_low_rating,
        active_flag=initial_active_flag,
        application_metadata=None,
    )

    vws_client.wait_for_target_processed(target_id=target_id)
    vws_client.update_target(
        target_id=target_id,
        active_flag=desired_active_flag,
    )

    target_details = vws_client.get_target_record(target_id=target_id)
    assert target_details.target_record.active_flag == desired_active_flag


@pytest.mark.parametrize(
    argnames="desired_active_flag",
    argvalues=["string", None],
)
def test_invalid(
    *,
    vws_client: VWS,
    target_id: str,
    desired_active_flag: str | None,
) -> None:
    """
    Values which are not Boolean values are not valid active
    flags.
    """
    with pytest.raises(expected_exception=FailError) as exc:
        _ = update_target(
            vws_client=vws_client,
            data={"active_flag": desired_active_flag},
            target_id=target_id,
            content_type="application/json",
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.BAD_REQUEST,
        result_code="Fail",
    )
