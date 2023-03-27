"""Matchers for query and duplicate requests."""

import io
from typing import Protocol, runtime_checkable

import imagehash
from PIL import Image


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
        breakpoint()
        database_image = Image.open(io.BytesIO(first_image_content))
        query_image = Image.open(io.BytesIO(second_image_content))
        database_hash = imagehash.average_hash(database_image)
        query_hash = imagehash.average_hash(query_image)
        return bool(database_hash - query_hash < self._threshold)
