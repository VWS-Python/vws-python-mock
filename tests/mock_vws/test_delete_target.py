"""
Tests for deleting targets.
"""

from http import HTTPStatus

import pytest
from vws import VWS
from vws.exceptions.vws_exceptions import (
    ProjectInactiveError,
    TargetStatusProcessingError,
    UnknownTargetError,
)

from mock_vws._constants import ResultCodes
from tests.mock_vws.utils.assertions import assert_vws_failure


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestDelete:
    """
    Tests for deleting targets.
    """

    @staticmethod
    def test_no_wait(target_id: str, vws_client: VWS) -> None:
        """When attempting to delete a target immediately after creating it, a
        `FORBIDDEN` response is returned.

        This is because the target goes into a processing state.

        There is a race condition here - if the target goes into a success or
        fail state before the deletion attempt.
        """
        with pytest.raises(
            expected_exception=TargetStatusProcessingError
        ) as exc:
            vws_client.delete_target(target_id=target_id)

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.FORBIDDEN,
            result_code=ResultCodes.TARGET_STATUS_PROCESSING,
        )

    @staticmethod
    def test_processed(target_id: str, vws_client: VWS) -> None:
        """
        When a target has finished processing, it can be deleted.
        """
        vws_client.wait_for_target_processed(target_id=target_id)
        vws_client.delete_target(target_id=target_id)

        with pytest.raises(expected_exception=UnknownTargetError):
            vws_client.get_target_record(target_id=target_id)


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestInactiveProject:
    """
    Tests for inactive projects.
    """

    @staticmethod
    def test_inactive_project(inactive_vws_client: VWS) -> None:
        """
        If the project is inactive, a FORBIDDEN response is returned.
        """
        target_id = "abc12345a"
        with pytest.raises(expected_exception=ProjectInactiveError) as exc:
            inactive_vws_client.delete_target(target_id=target_id)

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.FORBIDDEN,
            result_code=ResultCodes.PROJECT_INACTIVE,
        )
