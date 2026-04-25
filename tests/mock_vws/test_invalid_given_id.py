"""
Tests for passing invalid target IDs to endpoints which require a target
ID to
be given.
"""

from http import HTTPStatus

import pytest
from vws import VWS

from mock_vws._constants import ResultCodes
from tests.mock_vws.utils import Endpoint
from tests.mock_vws.utils.assertions import assert_vws_failure
from tests.mock_vws.utils.too_many_requests import handle_server_errors


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestInvalidGivenID:
    """
    Tests for giving an invalid ID to endpoints which require a target
    ID to be
    given.
    """

    @staticmethod
    def test_not_real_id(
        *,
        vws_client: VWS,
        endpoint: Endpoint,
        target_id: str,
    ) -> None:
        """
        A `NOT_FOUND` error is returned when an endpoint is given a
        target ID
        of a target which does not exist.
        """
        # This shared check only covers endpoints that end in target_id,
        # such as /targets/{target_id}. Endpoints with trailing segments
        # are covered by endpoint-specific tests.
        if not endpoint.path_url.endswith(target_id):
            return

        vws_client.wait_for_target_processed(target_id=target_id)
        vws_client.delete_target(target_id=target_id)

        response = endpoint.send()

        handle_server_errors(response=response)

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.NOT_FOUND,
            result_code=ResultCodes.UNKNOWN_TARGET,
        )
