"""Tests for inactive projects."""

import io
from http import HTTPStatus

import pytest
from vws import VWS
from vws.exceptions.vws_exceptions import (
    ProjectInactiveError,
)

from vws_mock_contract_tests.utils.assertions import (
    assert_vws_failure,
)


def test_inactive_project(
    *,
    image_file_failed_state: io.BytesIO,
    inactive_vws_client: VWS,
) -> None:
    """
    If the project is inactive, a FORBIDDEN response is
    returned.
    """
    with pytest.raises(expected_exception=ProjectInactiveError) as exc:
        _ = inactive_vws_client.add_target(
            name="example",
            width=1,
            image=image_file_failed_state,
            application_metadata=None,
            active_flag=True,
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.FORBIDDEN,
        result_code="ProjectInactive",
    )
