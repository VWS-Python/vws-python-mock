"""Matchers for query and duplicate requests."""

import io
from functools import cache
from typing import Protocol, runtime_checkable

import imagehash
from PIL import Image


@cache
def _average_hash_match(
    first_image_content: bytes,
    second_image_content: bytes,
) -> bool:
    """
    Whether one image's content matches another's closely enough.

    Args:
        first_image_content: One image's content.
        second_image_content: Another image's content.
    """
    first_image_file = io.BytesIO(initial_bytes=first_image_content)
    first_image = Image.open(fp=first_image_file)
    second_image_file = io.BytesIO(initial_bytes=second_image_content)
    second_image = Image.open(fp=second_image_file)
    first_image_hash = imagehash.average_hash(first_image)
    second_image_hash = imagehash.average_hash(second_image)
    return bool(first_image_hash == second_image_hash)


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


class AverageHashMatcher:
    """A matcher which returns whether two images are similar."""

    def __init__(self, threshold: int) -> None:
        """
        Args:
            threshold: The threshold for the average hash matcher.
        """
        self._threshold = threshold

    def __call__(
        self,
        first_image_content: bytes,
        second_image_content: bytes,
    ) -> bool:
        """
        Whether one image's content matches another's using an average hash.

        Args:
            first_image_content: One image's content.
            second_image_content: Another image's content.
        """
        return _average_hash_match(
            first_image_content=first_image_content,
            second_image_content=second_image_content,
        )
