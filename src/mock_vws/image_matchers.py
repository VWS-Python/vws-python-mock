"""Matchers for query and duplicate requests."""

import io
from typing import Protocol, runtime_checkable

import numpy as np
import torch
from beartype import beartype
from PIL import Image
from torchmetrics.image import (
    StructuralSimilarityIndexMeasure,
)


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
        first_image = Image.open(fp=first_image_file)
        second_image_file = io.BytesIO(initial_bytes=second_image_content)
        second_image = Image.open(fp=second_image_file)
        # Images must be the same size, and they must be larger than the
        # default SSIM window size of 11x11.
        target_size = (256, 256)
        first_image_resized = first_image.resize(size=target_size)
        second_image_resized = second_image.resize(size=target_size)

        first_image_np = np.array(object=first_image_resized, dtype=np.float32)
        first_image_tensor = torch.tensor(data=first_image_np).float() / 255
        first_image_tensor = first_image_tensor.view(
            first_image_resized.size[1],
            first_image_resized.size[0],
            len(first_image_resized.getbands()),
        )

        second_image_np = np.array(
            object=second_image_resized,
            dtype=np.float32,
        )
        second_image_tensor = torch.tensor(data=second_image_np).float() / 255
        second_image_tensor = second_image_tensor.view(
            second_image_resized.size[1],
            second_image_resized.size[0],
            len(second_image_resized.getbands()),
        )

        first_image_tensor_batch_dimension = first_image_tensor.permute(
            2,
            0,
            1,
        ).unsqueeze(dim=0)
        second_image_tensor_batch_dimension = second_image_tensor.permute(
            2,
            0,
            1,
        ).unsqueeze(dim=0)

        ssim = StructuralSimilarityIndexMeasure(data_range=1.0)
        ssim_value = ssim(
            first_image_tensor_batch_dimension,
            second_image_tensor_batch_dimension,
        )
        ssim_score = ssim_value.item()

        # Normalize SSIM score from -1 to 1 scale to 0 to 10 scale.
        # This maps -1 to 0 and 1 to 10.
        normalized_score = (ssim_score + 1) * 5
        minimum_acceptable_ssim_score = 7
        return bool(normalized_score > minimum_acceptable_ssim_score)
