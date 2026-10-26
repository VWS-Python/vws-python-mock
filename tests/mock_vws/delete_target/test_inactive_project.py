"""Tests for inactive projects."""

from http import HTTPStatus

import pytest
from vws import VWS
from vws.exceptions.vws_exceptions import (
    ProjectInactiveError,
)

from tests.mock_vws.utils.assertions import assert_vws_failure


def test_inactive_project(inactive_vws_client: VWS) -> None:
    """
    If the project is inactive, a FORBIDDEN response is
    returned.
    """
    target_id = "abc12345a"
    with pytest.raises(expected_exception=ProjectInactiveError) as exc:
        inactive_vws_client.delete_target(target_id=target_id)

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.FORBIDDEN,
        result_code="ProjectInactive",
    )
