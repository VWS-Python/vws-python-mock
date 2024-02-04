"""Matchers for query and duplicate requests."""

import io
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import piq  # type: ignore[import-untyped]
from PIL import Image
from torchvision.transforms import functional  # type: ignore[import-untyped]

if TYPE_CHECKING:
    import torch


@runtime_checkable
class ImageMatcher(Protocol):
    """Protocol for a matcher for query and duplicate requests."""

    def __call__(
        self,
        first_image_content: bytes,
        second_image_content: bytes,
    ) -> bool:
        """
        Whether one image's content matches another's closely enough.

        Args:
            first_image_content: One image's content.
            second_image_content: Another image's content.
        """
        # We disable a pylint warning here because the ellipsis is required
        # for pyright to recognize this as a protocol.
        ...  # pylint: disable=unnecessary-ellipsis


class ExactMatcher:
    """A matcher which returns whether two images are exactly equal."""

    def __call__(
        self,
        first_image_content: bytes,
        second_image_content: bytes,
    ) -> bool:
        """
        Whether one image's content matches another's exactly.

        Args:
            first_image_content: One image's content.
            second_image_content: Another image's content.
        """
        return bool(first_image_content == second_image_content)


class StructuralSimilarityMatcher:
    """A matcher which returns whether two images are similar using SSIM."""

    def __call__(
        self,
        first_image_content: bytes,
        second_image_content: bytes,
    ) -> bool:
        """
        Whether one image's content matches another's using a SSIM.

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
        first_image = first_image.resize(size=target_size)
        second_image = second_image.resize(size=target_size)

        # See https://github.com/pytorch/vision/pull/8251 for precise type.
        first_image_tensor = functional.to_tensor(pic=first_image)  # pyright: ignore[reportUnknownMemberType]
        second_image_tensor = functional.to_tensor(pic=second_image)  # pyright: ignore[reportUnknownMemberType]

        first_image_tensor_batch_dimension = first_image_tensor.unsqueeze(0)
        second_image_tensor_batch_dimension = second_image_tensor.unsqueeze(0)

        # See https://github.com/photosynthesis-team/piq/pull/377
        # for fixing the type hint in ``piq``.
        ssim_value: torch.Tensor = piq.ssim(  # pyright: ignore[reportAssignmentType]
            x=first_image_tensor_batch_dimension,
            y=second_image_tensor_batch_dimension,
            data_range=1.0,
        )
        ssim_score = ssim_value.item()

        # Normalize SSIM score from -1 to 1 scale to 0 to 10 scale.
        # This maps -1 to 0 and 1 to 10.
        normalized_score = (ssim_score + 1) * 5
        minimum_acceptable_ssim_score = 7
        return bool(normalized_score > minimum_acceptable_ssim_score)
