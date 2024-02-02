"""
Tests for target quality raters.
"""

from mock_vws.target_raters import RandomTargetTrackingRater


def test_random_target_tracking_rater() -> None:
    """
    Test that the random target tracking rater returns a random number.
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
