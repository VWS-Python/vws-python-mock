"""
Tests for passing invalid target IDs to endpoints which
require a target ID to be given.
"""
from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
import requests
from mock_vws._constants import ResultCodes

from tests.mock_vws.utils.assertions import assert_vws_failure
from tests.mock_vws.utils.too_many_requests import handle_server_errors

if TYPE_CHECKING:
    from vws import VWS

    from tests.mock_vws.utils import Endpoint


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestInvalidGivenID:
    """
    Tests for giving an invalid ID to endpoints which require a target ID to
    be given.
    """

    @staticmethod
    def test_not_real_id(
        vws_client: VWS,
        endpoint: Endpoint,
        target_id: str,
    ) -> None:
        """
        A `NOT_FOUND` error is returned when an endpoint is given a target ID
        of a target which does not exist.
        """
        if not endpoint.prepared_request.path_url.endswith(target_id):
            return

        vws_client.wait_for_target_processed(target_id=target_id)
        vws_client.delete_target(target_id=target_id)

        session = requests.Session()
        response = session.send(request=endpoint.prepared_request)
        handle_server_errors(response=response)

        assert_vws_failure(
            response=response,
            status_code=HTTPStatus.NOT_FOUND,
            result_code=ResultCodes.UNKNOWN_TARGET,
        )
