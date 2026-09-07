"""Tests for target ID validators."""

import pytest

from mock_vws._services_validators.target_validators import (
    target_id_from_path,
)


@pytest.mark.parametrize(
    argnames=("request_path", "target_id"),
    argvalues=[
        ("/targets/instances", "instances"),
        ("/targets/target123/instances", "target123"),
    ],
)
def test_target_id_from_path_uses_correct_path_segment(
    *,
    request_path: str,
    target_id: str,
) -> None:
    """The right target segment is used for both endpoint shapes."""
    assert target_id_from_path(request_path=request_path) == target_id
