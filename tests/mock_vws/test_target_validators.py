"""Tests for target ID validators."""

import pytest

from mock_vws._services_validators.target_validators import (
    validate_target_id_exists,
)
from mock_vws.database import CloudDatabase
from mock_vws.target import ImageTarget
from mock_vws.target_raters import HardcodedTargetTrackingRater
from tests.mock_vws.utils import make_image_file
from tests.mock_vws.verification import UnverifiedReason, mock_only

pytestmark = mock_only(
    reason=UnverifiedReason.NO_VUFORIA_CLAIM,
    detail="This covers an internal validator of the mock directly.",
)


def _database_with_target(*, target_id: str) -> CloudDatabase:
    """Create a database containing one target with the given ID."""
    target = ImageTarget(
        active_flag=True,
        application_metadata=None,
        image_value=make_image_file(
            file_format="PNG",
            color_space="RGB",
            width=8,
            height=8,
        ).getvalue(),
        name="example",
        processing_time_seconds=0,
        target_id=target_id,
        target_tracking_rater=HardcodedTargetTrackingRater(rating=5),
        width=1,
    )
    return CloudDatabase(targets={target})


@pytest.mark.parametrize(
    argnames=("request_path", "target_id"),
    argvalues=[
        ("/targets/instances", "instances"),
        ("/targets/target123/instances", "target123"),
    ],
)
def test_validate_target_id_exists_uses_correct_path_segment(
    *,
    request_path: str,
    target_id: str,
) -> None:
    """Validation uses the right target segment for both endpoint
    shapes.
    """
    database = _database_with_target(target_id=target_id)

    validate_target_id_exists(
        request_path=request_path,
        database=database,
    )
