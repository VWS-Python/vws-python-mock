"""
Tests for passing invalid target IDs to endpoints which require a target
ID to
be given.
"""

import io
from http import HTTPStatus
from types import SimpleNamespace

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
        vws_client: VWS,
        endpoint: Endpoint,
        target_id: str,
    ) -> None:
        """
        A `NOT_FOUND` error is returned when an endpoint is given a
        target ID
        of a target which does not exist.
        """
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


@pytest.mark.usefixtures("mock_only_vuforia")
class TestTargetIdNamedInstances:
    """Regression tests for a target ID with value ``instances``."""

    @staticmethod
    def test_summary_path_handles_target_id_named_instances(
        monkeypatch: pytest.MonkeyPatch,
        image_file_success_state_low_rating: io.BytesIO,
        vws_client: VWS,
    ) -> None:
        """`/summary/{target_id}` should use the final path segment as
        ID.
        """
        target_id = "instances"
        monkeypatch.setattr(
            "mock_vws.target.uuid.uuid4",
            lambda: SimpleNamespace(hex=target_id),
        )

        created_target_id = vws_client.add_target(
            name="example_target",
            width=1,
            image=image_file_success_state_low_rating,
            active_flag=True,
            application_metadata=None,
        )
        assert created_target_id == target_id

        vws_client.wait_for_target_processed(target_id=created_target_id)
        report = vws_client.get_target_summary_report(
            target_id=created_target_id,
        )
        assert report.target_name == "example_target"
