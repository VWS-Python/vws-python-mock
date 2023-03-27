"""Raters for target quality."""

import io
import math
import random
from typing import Protocol, runtime_checkable

import brisque
import cv2
import numpy as np
from PIL import Image


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
        image_file = io.BytesIO(initial_bytes=image_content)
        image = Image.open(fp=image_file)
        image_array = np.asarray(a=image)
        obj = brisque.BRISQUE(url=False)
        # We avoid a barrage of warnings from the BRISQUE library.
        with np.errstate(divide="ignore", invalid="ignore"):
            try:
                score = obj.score(img=image_array)
            except cv2.error:  # pylint: disable=no-member
                return 0
        if math.isnan(score):
            return 0
        return int(score / 20)
