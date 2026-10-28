"""Tests for inactive projects."""

import uuid

import pytest
from vws import VWS
from vws.exceptions.vws_exceptions import ProjectInactiveError


def test_inactive_project(inactive_vws_client: VWS) -> None:
    """
    If the project is inactive, a FORBIDDEN response is
    returned.
    """
    with pytest.raises(expected_exception=ProjectInactiveError):
        _ = inactive_vws_client.get_duplicate_targets(
            target_id=uuid.uuid4().hex,
        )
