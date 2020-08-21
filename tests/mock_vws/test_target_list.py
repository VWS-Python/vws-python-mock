"""
Tests for the mock of the target list endpoint.
"""

from http import HTTPStatus

import pytest
from vws import VWS

from mock_vws._constants import ResultCodes
from mock_vws.database import VuforiaDatabase
from tests.mock_vws.utils import (
    list_targets,
)
from tests.mock_vws.utils.assertions import assert_vws_response


@pytest.mark.usefixtures('verify_mock_vuforia')
class TestTargetList:
    """
    Tests for the mock of the database summary endpoint at `/summary`.
    """

    def test_success(
        self,
        vuforia_database: VuforiaDatabase,
    ) -> None:
        """
        It is possible to get a success response.
        """
        response = list_targets(vuforia_database=vuforia_database)
        assert_vws_response(
            response=response,
            status_code=HTTPStatus.OK,
            result_code=ResultCodes.SUCCESS,
        )
        expected_keys = {'result_code', 'transaction_id', 'results'}
        assert response.json().keys() == expected_keys
        assert response.json()['results'] == []

    def test_includes_targets(
        self,
        vuforia_database: VuforiaDatabase,
        target_id: str,
    ) -> None:
        """
        Targets in the database are returned in the list.
        """
        response = list_targets(vuforia_database=vuforia_database)
        assert response.json()['results'] == [target_id]

    def test_deleted(
        self,
        vuforia_database: VuforiaDatabase,
        target_id: str,
    ) -> None:
        """
        Deleted targets are not returned in the list.
        """
        vws_client = VWS(
            server_access_key=vuforia_database.server_access_key,
            server_secret_key=vuforia_database.server_secret_key,
        )
        vws_client.wait_for_target_processed(target_id=target_id)
        vws_client.delete_target(target_id=target_id)
        response = list_targets(vuforia_database=vuforia_database)
        assert response.json()['results'] == []


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
        The project's active state does not affect the target list.
        """
        response = list_targets(vuforia_database=inactive_database)
        assert_vws_response(
            response=response,
            status_code=HTTPStatus.OK,
            result_code=ResultCodes.SUCCESS,
        )
