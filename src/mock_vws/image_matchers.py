"""Matchers for query and duplicate requests."""

import io
import statistics
from typing import Protocol, runtime_checkable

import cv2
import numpy as np
from beartype import beartype

from mock_vws._image_opening import open_image


@runtime_checkable
class ImageMatcher(Protocol):
    """Protocol for a matcher for query and duplicate requests."""

    def __call__(
        self,
        first_image_content: bytes,
        second_image_content: bytes,
    ) -> float | None:
        """How closely one image's content matches another's.

        Args:
            first_image_content: One image's content.
            second_image_content: Another image's content.

        Returns:
            A score for the match, where a higher score is a better match,
            or ``None`` if the images do not match closely enough to be
            considered a match at all.

            Matches are returned best score first, so a matcher which gives
            every match the same score leaves the order of its matches to
            the mock's tie-break: upload date and then target ID.
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
    ) -> float | None:
        """Whether one image's content matches another's exactly.

        Args:
            first_image_content: One image's content.
            second_image_content: Another image's content.

        Returns:
            ``1.0`` if the images are exactly equal, else ``None``.  Every
            match therefore has the same score.
        """
        if first_image_content == second_image_content:
            return 1.0
        return None


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
    ) -> float | None:
        """Whether one image's content matches another's using a SSIM.

        Args:
            first_image_content: One image's content.
            second_image_content: Another image's content.

        Returns:
            The images' SSIM score if they match, else ``None``.  A higher
            SSIM score means that the images are more similar.
        """
        first_image_file = io.BytesIO(initial_bytes=first_image_content)
        second_image_file = io.BytesIO(initial_bytes=second_image_content)
        with (
            open_image(fp=first_image_file) as first_image,
            open_image(fp=second_image_file) as second_image,
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
        if ssim_score > minimum_acceptable_ssim_score:
            return ssim_score
        return None
