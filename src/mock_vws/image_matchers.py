"""Matchers for query and duplicate requests."""

import io
import statistics
from typing import Protocol, runtime_checkable

import cv2
import numpy as np
from beartype import beartype
from PIL import Image


@runtime_checkable
class ImageMatcher(Protocol):
    """Protocol for a matcher for query and duplicate requests."""

    def __call__(
        self,
        first_image_content: bytes,
        second_image_content: bytes,
    ) -> bool:
        """Whether one image's content matches another's closely enough.

        Args:
            first_image_content: One image's content.
            second_image_content: Another image's content.
        """
        # We disable a pylint warning here because the ellipsis is required
        # for pyright to recognize this as a protocol.
        ...  # pylint: disable=unnecessary-ellipsis


@beartype
class ExactMatcher:
    """A matcher which returns whether two images are exactly equal."""

    def __call__(
        self,
        first_image_content: bytes,
        second_image_content: bytes,
    ) -> bool:
        """Whether one image's content matches another's exactly.

        Args:
            first_image_content: One image's content.
            second_image_content: Another image's content.
        """
        return bool(first_image_content == second_image_content)


@beartype
class StructuralSimilarityMatcher:
    """
    A matcher which returns whether two images are similar using
    SSIM.
    """

    def __call__(
        self,
        first_image_content: bytes,
        second_image_content: bytes,
    ) -> bool:
        """Whether one image's content matches another's using a SSIM.

        Args:
            first_image_content: One image's content.
            second_image_content: Another image's content.
        """
        first_image_file = io.BytesIO(initial_bytes=first_image_content)
        second_image_file = io.BytesIO(initial_bytes=second_image_content)
        with (
            Image.open(fp=first_image_file) as first_image,
            Image.open(fp=second_image_file) as second_image,
        ):
            # Images must be the same size, and they must be larger than the
            # default SSIM window size of 11x11.
            target_size = (256, 256)
            first_image_array = np.asarray(
                a=first_image.resize(size=target_size).convert(mode="RGB"),
            )
            second_image_array = np.asarray(
                a=second_image.resize(size=target_size).convert(mode="RGB"),
            )

        quality_ssim = cv2.quality.QualitySSIM.create(
            ref=first_image_array,
        )
        channel_scores = quality_ssim.compute(cmp=second_image_array)
        ssim_score = statistics.fmean(data=channel_scores[:3])

        # The old normalized > 7 threshold is equivalent to a raw SSIM > 0.4.
        minimum_acceptable_ssim_score = 0.4
        return ssim_score > minimum_acceptable_ssim_score
