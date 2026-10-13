"""Tests for target quality raters."""

import io

import pytest

from mock_vws._target_tracking_rating import rating_from_brisque_score
from mock_vws.target import ImageTarget
from mock_vws.target_raters import (
    BrisqueTargetTrackingRater,
    HardcodedTargetTrackingRater,
    RandomTargetTrackingRater,
)
from tests.mock_vws.utils import make_single_color_image_file


@pytest.mark.parametrize(
    argnames=("brisque_score", "expected_rating"),
    argvalues=[
        (-20.0, 5),
        (0.0, 5),
        (19.99, 5),
        (20.0, 4),
        (79.99, 2),
        (80.0, 1),
        (99.99, 1),
        (100.0, 0),
        (120.0, 0),
        (float("nan"), 0),
        (float("inf"), 0),
        (float("-inf"), 0),
    ],
)
def test_brisque_score_conversion(
    *,
    brisque_score: float,
    expected_rating: int,
) -> None:
    """Scores map to bounded ratings, with undefined scores rated zero."""
    assert (
        rating_from_brisque_score(brisque_score=brisque_score)
        == expected_rating
    )


@pytest.mark.parametrize(
    argnames=("width", "height"),
    argvalues=[(1, 1), (32, 32), (256, 128)],
)
def test_image_without_contrast(*, width: int, height: int) -> None:
    """An image with an undefined BRISQUE score has rating zero."""
    image_file = make_single_color_image_file(width=width, height=height)
    rater = BrisqueTargetTrackingRater()
    assert rater(image_content=image_file.getvalue()) == 0


def test_processed_image_without_contrast_serializes() -> None:
    """A processed uniform target can be listed with rating zero."""
    image_file = make_single_color_image_file(width=32, height=32)
    target = ImageTarget(
        name="uniform-target",
        active_flag=True,
        application_metadata=None,
        width=1,
        image_value=image_file.getvalue(),
        processing_time_seconds=0,
        target_tracking_rater=BrisqueTargetTrackingRater(),
    )
    assert target.to_dict()["tracking_rating"] == 0


def test_random_target_tracking_rater() -> None:
    """
    Test that the random target tracking rater returns a random
    number.
    """
    rater = RandomTargetTrackingRater()
    image_content = b"content"
    # We do not test that the number is truly random, but we think that if we
    # try this a number of times, it is highly likely that the numbers will not
    # all be the same.
    ratings = [rater(image_content=image_content) for _ in range(50)]
    sorted_ratings = sorted(ratings)
    lowest_rating = sorted_ratings[0]
    highest_rating = sorted_ratings[-1]
    minimum_rating = 0
    maximum_rating = 5
    assert lowest_rating >= minimum_rating
    assert highest_rating <= maximum_rating
    assert lowest_rating != highest_rating


@pytest.mark.parametrize(argnames="rating", argvalues=range(-10, 10))
def test_hardcoded_target_tracking_rater(rating: int) -> None:
    """
    Test that the hardcoded target tracking rater returns the hardcoded
    number.
    """
    rater = HardcodedTargetTrackingRater(rating=rating)
    image_content = b"content"
    ratings = [rater(image_content=image_content) for _ in range(50)]
    assert all(given_rating == rating for given_rating in ratings)


def test_low_quality_image(
    image_file_success_state_low_rating: io.BytesIO,
) -> None:
    """Test that a low quality image returns a low rating."""
    rater = BrisqueTargetTrackingRater()
    image_content = image_file_success_state_low_rating.getvalue()
    rating = rater(image_content=image_content)
    assert rating == 0


def test_high_quality_image(high_quality_image: io.BytesIO) -> None:
    """Test that a high quality image returns a high rating."""
    rater = BrisqueTargetTrackingRater()
    image_content = high_quality_image.getvalue()
    rating = rater(image_content=image_content)
    assert rating > 1


def test_different_high_quality_image(
    different_high_quality_image: io.BytesIO,
) -> None:
    """Test that a high quality image returns a high rating."""
    rater = BrisqueTargetTrackingRater()
    image_content = different_high_quality_image.getvalue()
    rating = rater(image_content=image_content)
    assert rating > 1
