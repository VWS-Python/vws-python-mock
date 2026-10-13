"""Tests for deleting targets."""

from http import HTTPStatus

import pytest
from vws import VWS
from vws.exceptions.vws_exceptions import (
    TargetStatusProcessingError,
    UnknownTargetError,
)

from mock_vws._constants import ResultCodes
from tests.mock_vws.utils.assertions import assert_vws_failure


def test_no_wait(
    *,
    unprocessed_target_id: str,
    vws_client: VWS,
) -> None:
    """When attempting to delete a target immediately after creating
    it, a
    `FORBIDDEN` response is returned.

    This is because the target goes into a processing state.

    There is a race condition here - if the target goes into a success or
    fail state before the deletion attempt.
    """
    with pytest.raises(expected_exception=TargetStatusProcessingError) as exc:
        vws_client.delete_target(target_id=unprocessed_target_id)

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.FORBIDDEN,
        result_code=ResultCodes.TARGET_STATUS_PROCESSING,
    )


def test_processed(*, target_id: str, vws_client: VWS) -> None:
    """When a target has finished processing, it can be deleted."""
    vws_client.delete_target(target_id=target_id)

    with pytest.raises(expected_exception=UnknownTargetError):
        _ = vws_client.get_target_record(target_id=target_id)
