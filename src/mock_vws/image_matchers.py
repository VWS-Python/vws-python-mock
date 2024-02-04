"""Matchers for query and duplicate requests."""

import io
from functools import cache
from typing import Protocol, runtime_checkable

import numpy as np
from imagehash import ANTIALIAS, ImageHash
from PIL import Image


def _average_hash(image: Image.Image) -> ImageHash:
    """
    Average Hash computation.

    This is taken from `imagehash`'s `average_hash` function, but is modified
    so that we can use pyright in strict mode without error..
    See https://github.com/JohannesBuchner/imagehash/issues/206.

    Implementation follows https://www.hackerfactor.com/blog/index.php?/archives/432-Looks-Like-It.html

    Step by step explanation: https://web.archive.org/web/20171112054354/https://www.safaribooksonline.com/blog/2013/11/26/image-hashing-with-python/
    """
    hash_size = 8
    # reduce size and complexity, then convert to greyscale
    image = image.convert("L").resize((hash_size, hash_size), ANTIALIAS)

    # find average pixel value; 'pixels' is an array of the pixel values,
    # ranging from 0 (black) to 255 (white)
    pixels = np.asarray(image)
    avg = np.mean(pixels)

    # create string of bits
    diff = pixels > avg
    # make a hash
    return ImageHash(diff)


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
    first_image_hash = _average_hash(first_image)
    second_image_hash = _average_hash(second_image)
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
