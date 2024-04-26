"""Raters for target quality."""

import secrets
from typing import Protocol, runtime_checkable


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
        return secrets.randbelow(exclusive_upper_bound=6)


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
