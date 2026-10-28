"""
Tests which exercise the target tracking_rating, and check the image
fixtures we use.
"""

import io

from vws import VWS

from vws_mock_contract_tests.get_target.helpers import (
    get_target_tracking_rating,
)


def test_target_quality(
    *,
    vws_client: VWS,
    high_quality_image: io.BytesIO,
    image_file_success_state_low_rating: io.BytesIO,
) -> None:
    """The target tracking rating is as expected."""
    high_quality_image_tracking_rating = get_target_tracking_rating(
        vws_client=vws_client,
        image_file=high_quality_image,
    )
    low_quality_image_tracking_rating = get_target_tracking_rating(
        vws_client=vws_client,
        image_file=image_file_success_state_low_rating,
    )
    assert (
        high_quality_image_tracking_rating > low_quality_image_tracking_rating
    )
