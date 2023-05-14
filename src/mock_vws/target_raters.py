"""Raters for target quality."""

import functools
import io
import math
import random
from typing import Protocol, runtime_checkable

import brisque
import cv2
import numpy as np
from PIL import Image

# cv2 errors cannot be inferred without type stubs.
# See https://github.com/opencv/opencv/issues/14590.
_CV2_ERROR = (
    cv2.error  # pyright: ignore[reportGeneralTypeIssues] # noqa: E501 # pylint: disable=no-member
)


@functools.cache
def _get_brisque_target_tracking_rating(image_content: bytes) -> int:
    """
    Get a target tracking rating based on a BRISQUE score.

    This is a rough approximation of the quality score used by Vuforia, but is
    not accurate. For example, our "corrupted_image" rating is based on a
    BRISQUE score of 0, but Vuforia's is 1.

    Args:
        image_content: A target's image's content.
    """
    image_file = io.BytesIO(initial_bytes=image_content)
    image = Image.open(fp=image_file)
    image_array = np.asarray(a=image)
    brisque_obj = brisque.BRISQUE(url=False)
    # We avoid a barrage of warnings from the BRISQUE library.
    with np.errstate(divide="ignore", invalid="ignore"):
        try:
            score = brisque_obj.score(img=image_array)
        except (_CV2_ERROR, ValueError):
            return 0
    if math.isnan(score):
        return 0
    brisque_max_score = 100
    tracking_rating_max = 5
    return int(score / (brisque_max_score / tracking_rating_max))


@runtime_checkable
class TargetTrackingRater(Protocol):
    """Protocol for a rater of target quality."""

    def __call__(self, image_content: bytes) -> int:
        """
        The target tracking rating.

        Args:
            image_content: A target's image's content.
        """
        # We disable a pylint warning here because the ellipsis is required
        # for pyright to recognize this as a protocol.
        ...  # pylint: disable=unnecessary-ellipsis


class RandomTargetTrackingRater:
    """A rater which returns a random number."""

    def __call__(self, image_content: bytes) -> int:
        """
        A random target tracking rating.

        Args:
            image_content: A target's image's content.
        """
        assert image_content
        return random.randint(0, 5)


class HardcodedTargetTrackingRater:
    """A rater which returns a hardcoded number."""

    def __init__(self, rating: int) -> None:
        """
        Args:
            rating: The rating to return.
        """
        self._rating = rating

    def __call__(self, image_content: bytes) -> int:
        """
        A random target tracking rating.

        Args:
            image_content: A target's image's content.
        """
        assert image_content
        return self._rating


class BrisqueTargetTrackingRater:
    """A rater which returns a rating based on a BRISQUE score."""

    def __call__(self, image_content: bytes) -> int:
        """
        A rating based on a BRISQUE score.

        This is a rough approximation of the quality score used by Vuforia, but
        is not accurate. For example, our "corrupted_image" fixture is rated as
        -2 by Vuforia, but is rated as 0 by this function.

        Args:
            image_content: A target's image's content.
        """
        return _get_brisque_target_tracking_rating(image_content=image_content)
