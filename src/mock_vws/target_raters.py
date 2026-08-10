"""Raters for target quality."""

import functools
import io
import math
import secrets
import warnings
from typing import Protocol, runtime_checkable

from beartype import beartype
from pyteenybrisque import score

from mock_vws._image_opening import open_image


@functools.cache
@beartype
def _get_brisque_target_tracking_rating(*, image_content: bytes) -> int:
    """Get a target tracking rating based on a BRISQUE score.

    This is a rough approximation of the quality score used by Vuforia, but is
    not accurate. For example, our "corrupted_image" rating is based on a
    BRISQUE score of 0, but Vuforia's is 1.

    Args:
        image_content: A target's image's content.
    """
    image_file = io.BytesIO(initial_bytes=image_content)
    with open_image(fp=image_file) as image, warnings.catch_warnings():
        # Uniform images produce a zero-variance warning and non-finite score.
        warnings.simplefilter(action="ignore", category=RuntimeWarning)
        try:
            brisque_score = score(image=image)
        except ZeroDivisionError:
            # An image of a single color divides by zero rather than giving a
            # non-finite score.
            return 0

    if not math.isfinite(brisque_score):
        return 0

    # BRISQUE ranges from 0 (best) to 100 (worst), while Vuforia's target
    # tracking rating ranges from 0 (worst) to 5 (best).
    rating = 5 - math.floor(brisque_score / 20)
    return min(5, max(0, rating))


@runtime_checkable
class TargetTrackingRater(Protocol):
    """Protocol for a rater of target quality."""

    def __call__(self, image_content: bytes) -> int:
        """The target tracking rating.

        Args:
            image_content: A target's image's content.
        """
        # We disable a pylint warning here because the ellipsis is required
        # for pyright to recognize this as a protocol.
        ...  # pylint: disable=unnecessary-ellipsis


@beartype
class RandomTargetTrackingRater:
    """A rater which returns a random number."""

    def __call__(self, image_content: bytes) -> int:
        """A random target tracking rating.

        Args:
            image_content: A target's image's content.
        """
        del image_content
        return secrets.randbelow(exclusive_upper_bound=6)


@beartype
class HardcodedTargetTrackingRater:
    """A rater which returns a hardcoded number."""

    def __init__(self, rating: int) -> None:
        """
        Args:
            rating: The rating to return.
        """
        self._rating = rating

    def __call__(self, image_content: bytes) -> int:
        """A random target tracking rating.

        Args:
            image_content: A target's image's content.
        """
        del image_content
        return self._rating


@beartype
class BrisqueTargetTrackingRater:
    """A rater which returns a rating based on a BRISQUE score."""

    def __call__(self, image_content: bytes) -> int:
        """A rating based on a BRISQUE score.

        This is a rough approximation of the quality score used by Vuforia, but
        is not accurate. For example, our "corrupted_image" fixture is rated as
        -2 by Vuforia, but is rated as 0 by this function.

        Args:
            image_content: A target's image's content.
        """
        return _get_brisque_target_tracking_rating(image_content=image_content)
