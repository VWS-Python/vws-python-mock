"""Tests for inactive projects."""

import uuid

import pytest
from vws import VWS
from vws.exceptions.vws_exceptions import UnknownTargetError


def test_inactive_project(inactive_vws_client: VWS) -> None:
    """The project's active state does not affect getting a target."""
    with pytest.raises(expected_exception=UnknownTargetError):
        _ = inactive_vws_client.get_target_record(target_id=uuid.uuid4().hex)
