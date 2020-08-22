"""
Tests for deleting targets.
"""

from http import HTTPStatus

import pytest
from vws import VWS
from vws.exceptions import (
    ProjectInactive,
    TargetStatusProcessing,
    UnknownTarget,
)

from mock_vws._constants import ResultCodes
from mock_vws.database import VuforiaDatabase
from tests.mock_vws.utils.assertions import assert_vws_failure


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestDelete:
    """
    Tests for deleting targets.
    """

    def test_no_wait(
        self,
        target_id: str,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        When attempting to delete a target immediately after creating it, a
        `FORBIDDEN` response is returned.

        This is because the target goes into a processing state.

        There is a race condition here - if the target goes into a success or
        fail state before the deletion attempt.
        """
        vws_client = VWS(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key=vuforia_database.server_secret_key,
        )
        with pytest.raises(TargetStatusProcessing) as exc:
            vws_client.delete_target(target_id=target_id)

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.FORBIDDEN,
            result_code=ResultCodes.TARGET_STATUS_PROCESSING,
        )

    def test_processed(
        self,
        target_id: str,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        When a target has finished processing, it can be deleted.
        """
        vws_client = VWS(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key=vuforia_database.server_secret_key,
        )
        vws_client.wait_for_target_processed(target_id=target_id)
        vws_client.delete_target(target_id=target_id)

        with pytest.raises(UnknownTarget):
            vws_client.get_target_record(target_id=target_id)


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestInactiveProject:
    """
    Tests for inactive projects.
    """

    def test_inactive_project(
        self,
        inactive_database: VuforiaDatabase,
    ) -> None:
        """
        If the project is inactive, a FORBIDDEN response is returned.
        """
        target_id = 'abc12345a'
        vws_client = VWS(
            server_access_key=inactive_database.server_access_key,
            server_secret_key=inactive_database.server_secret_key,
        )
        with pytest.raises(ProjectInactive) as exc:
            vws_client.delete_target(target_id=target_id)

        assert_vws_failure(
            response=exc.value.response,
            status_code=HTTPStatus.FORBIDDEN,
            result_code=ResultCodes.PROJECT_INACTIVE,
        )
