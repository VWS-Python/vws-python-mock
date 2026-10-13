"""Tests for updating targets."""

import io
import json
from http import HTTPStatus

import pytest
from vws import VWS
from vws.exceptions.vws_exceptions import (
    AuthenticationFailureError,
    TargetStatusNotSuccessError,
)
from vws.reports import TargetStatuses

from mock_vws._constants import ResultCodes
from tests.mock_vws.update_target.helpers import (
    update_target,
)
from tests.mock_vws.utils.assertions import (
    assert_vws_failure,
    assert_vws_response,
)


@pytest.mark.parametrize(
    argnames="content_type",
    argvalues=[
        # This is the documented required content type:
        "application/json",
        # Other content types also work.
        "other/content_type",
    ],
    ids=["Documented Content-Type", "Undocumented Content-Type"],
)
def test_content_types(
    *,
    vws_client: VWS,
    image_file_failed_state: io.BytesIO,
    content_type: str,
) -> None:
    """
    The ``Content-Type`` header does not change the response as long
    as it
    is not empty.
    """
    target_id = vws_client.add_target(
        name="example",
        width=1,
        image=image_file_failed_state,
        active_flag=True,
        application_metadata=None,
    )

    with pytest.raises(expected_exception=TargetStatusNotSuccessError) as exc:
        _ = update_target(
            vws_client=vws_client,
            data={"name": "Adam"},
            target_id=target_id,
            content_type=content_type,
        )

    # Code is FORBIDDEN because the target is processing.
    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.FORBIDDEN,
        result_code=ResultCodes.TARGET_STATUS_NOT_SUCCESS,
    )


def test_empty_content_type(
    *,
    vws_client: VWS,
    image_file_failed_state: io.BytesIO,
) -> None:
    """
    An ``UNAUTHORIZED`` response is given if an empty ``Content-
    Type``
    header is given.
    """
    target_id = vws_client.add_target(
        name="example",
        width=1,
        image=image_file_failed_state,
        active_flag=True,
        application_metadata=None,
    )

    with pytest.raises(expected_exception=AuthenticationFailureError) as exc:
        _ = update_target(
            vws_client=vws_client,
            data={"name": "Adam"},
            target_id=target_id,
            content_type="",
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.UNAUTHORIZED,
        result_code=ResultCodes.AUTHENTICATION_FAILURE,
    )


def test_no_fields_given(
    *,
    vws_client: VWS,
    target_id: str,
) -> None:
    """No data fields are required."""
    response = update_target(
        vws_client=vws_client,
        data={},
        target_id=target_id,
        content_type="application/json",
    )

    assert_vws_response(
        response=response,
        status_code=HTTPStatus.OK,
        result_code=ResultCodes.SUCCESS,
    )

    response_json = json.loads(s=response.text)
    assert isinstance(response_json, dict)
    assert response_json.keys() == {"result_code", "transaction_id"}

    target_details = vws_client.get_target_record(target_id=target_id)
    # Targets go back to processing after being updated.
    assert target_details.status == TargetStatuses.PROCESSING

    vws_client.wait_for_target_processed(target_id=target_id)

    target_details = vws_client.get_target_record(target_id=target_id)
    assert target_details.status == TargetStatuses.SUCCESS
