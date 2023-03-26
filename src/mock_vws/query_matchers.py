"""Matchers for query requests."""

import io
from typing import Protocol, runtime_checkable

import imagehash
from PIL import Image


@runtime_checkable
class QueryMatcher(Protocol):
    """Protocol for a matcher for query requests."""

    def __call__(
        self,
        database_image_content: bytes,
        query_image_content: bytes,
    ) -> bool:
        """
        Return whether the given database image content matches the given query
        image.

        Args:
            database_image_content: The image content from an image in the
                database.
            query_image_content: The image content from a query.
        """
        # We disable a pylint warning here because the ellipsis is required
        # for pyright to recognize this as a protocol.
        ...  # pylint: disable=unnecessary-ellipsis


class ExactMatcher:
    """A matcher which returns whether two images are exactly equal."""

    def __call__(
        self,
        database_image_content: bytes,
        query_image_content: bytes,
    ) -> bool:
        """
        Return whether the given database image content matches the given query
        image exactly.

        Args:
            database_image_content: The image content from an image in the
                database.
            query_image_content: The image content from a query.
        """
        return bool(database_image_content == query_image_content)


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
        database_image_content: bytes,
        query_image_content: bytes,
    ) -> bool:
        """
        Return whether the given database image content matches the given query
        image.

        Args:
            database_image_content: The image content from an image in the
                database.
            query_image_content: The image content from a query.
        """
        database_image = Image.open(io.BytesIO(database_image_content))
        query_image = Image.open(io.BytesIO(query_image_content))
        database_hash = imagehash.average_hash(database_image)
        query_hash = imagehash.average_hash(query_image)
        return bool(database_hash - query_hash < self._threshold)
