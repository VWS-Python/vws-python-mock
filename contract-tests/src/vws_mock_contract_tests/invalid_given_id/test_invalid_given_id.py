"""
Tests for giving an invalid ID to endpoints which require a target
ID to be
given.
"""

from http import HTTPStatus

from vws import VWS

from vws_mock_contract_tests.utils import Endpoint
from vws_mock_contract_tests.utils.assertions import assert_vws_failure
from vws_mock_contract_tests.utils.too_many_requests import (
    handle_server_errors,
)


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

    vws_client.delete_target(target_id=target_id)

    response = endpoint.send()

    handle_server_errors(response=response)

    assert_vws_failure(
        response=response,
        status_code=HTTPStatus.NOT_FOUND,
        result_code="UnknownTarget",
    )
