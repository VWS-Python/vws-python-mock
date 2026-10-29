"""Tests for targets through the `requests-mock` backend."""

import json

import pytest
from freezegun import freeze_time
from vws.reports import TargetStatuses

from mock_vws.target import VuMarkTarget


def test_vumark_target_to_dict() -> None:
    """It is possible to dump a VuMark target to a dictionary and
    load it back.
    """
    vumark_target = VuMarkTarget(
        name="example-vumark",
        processing_time_seconds=5.0,
    )
    target_dict = vumark_target.to_dict()

    assert bool(json.dumps(obj=target_dict))

    new_target = VuMarkTarget.from_dict(target_dict=target_dict)
    assert new_target == vumark_target


@pytest.mark.parametrize(
    argnames="server_time",
    argvalues=[
        "2026-10-08 12:00:00",
        "2026-10-08 12:00:00.500000",
        "2026-10-08 12:00:01",
    ],
    ids=["behind", "equal", "ahead"],
)
def test_zero_processing_vumark_target_status(server_time: str) -> None:
    """Zero-duration targets succeed regardless of the server clock."""
    with freeze_time(time_to_freeze="2026-10-08 12:00:00.500000"):
        target_dict = VuMarkTarget(name="example").to_dict()

    with freeze_time(time_to_freeze=server_time):
        target = VuMarkTarget.from_dict(target_dict=target_dict)
        assert target.status == TargetStatuses.SUCCESS.value


@pytest.mark.parametrize(
    argnames=("server_time", "expected_status"),
    argvalues=[
        ("2026-10-08 11:59:59.500000", TargetStatuses.PROCESSING),
        ("2026-10-08 12:00:00", TargetStatuses.PROCESSING),
        ("2026-10-08 12:00:00.499999", TargetStatuses.PROCESSING),
        ("2026-10-08 12:00:00.500000", TargetStatuses.SUCCESS),
        ("2026-10-08 12:00:00.500001", TargetStatuses.SUCCESS),
    ],
    ids=["behind", "equal", "before-completion", "at-completion", "after"],
)
def test_positive_processing_vumark_target_status(
    *, server_time: str, expected_status: TargetStatuses
) -> None:
    """A positive duration finishes at the exact completion timestamp."""
    with freeze_time(time_to_freeze="2026-10-08 12:00:00"):
        target_dict = VuMarkTarget(
            name="example", processing_time_seconds=0.5
        ).to_dict()

    with freeze_time(time_to_freeze=server_time):
        target = VuMarkTarget.from_dict(target_dict=target_dict)
        assert target.status == expected_status.value


# Tests for setting the recognition counts of a target.

_CURRENT_MONTH_RECOS = 3
_PREVIOUS_MONTH_RECOS = 5
_TOTAL_RECOS = 8
