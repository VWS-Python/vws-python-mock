"""Raters for target quality."""

import functools
import io
import math
import secrets
from typing import Protocol, runtime_checkable

import numpy as np
import torch
from beartype import beartype
from PIL import Image
from piq.brisque import brisque  # pyright: ignore[reportMissingTypeStubs]


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
    image = Image.open(fp=image_file)
    image_np = np.array(object=image, dtype=np.float32)
    image_tensor = torch.tensor(data=image_np).float() / 255
    image_tensor = image_tensor.view(
        image.size[1],
        image.size[0],
        len(image.getbands()),
    )
    image_tensor = image_tensor.permute(2, 0, 1).unsqueeze(dim=0)
    try:
        brisque_score = brisque(x=image_tensor, data_range=255)
    except (AssertionError, IndexError):
        return 0
    return math.ceil(int(brisque_score.item()) / 20)


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
