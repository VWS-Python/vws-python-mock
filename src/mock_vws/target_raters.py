"""Raters for target quality."""

import functools
import io
import math
import random
from typing import Protocol, runtime_checkable

import piq  # type: ignore[import-untyped]
from PIL import Image
from torchvision.transforms import functional  # type: ignore[import-untyped]


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
    # See https://github.com/pytorch/vision/pull/8251 for precise type.
    image_tensor = functional.to_tensor(pic=image) * 255  # pyright: ignore[reportUnknownMemberType]
    image_tensor = image_tensor.unsqueeze(0)
    try:
        brisque_score = piq.brisque(x=image_tensor, data_range=255)
    except AssertionError:
        return 0
    return math.ceil(int(brisque_score.item()) / 20)


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
