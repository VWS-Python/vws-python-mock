"""Open images without Pillow's decompression bomb protection."""

import contextlib
import threading
from collections.abc import Generator
from typing import IO

from PIL import Image

# ``Image.MAX_IMAGE_PIXELS`` is a module level setting, so it is changed for
# as short a time as possible, and only by one thread at a time.
_MAX_IMAGE_PIXELS_LOCK = threading.Lock()


# This is not decorated with ``@beartype`` because beartype does not accept
# an ``io.BytesIO`` for an ``IO[bytes]`` parameter, and that is what most
# callers give.
@contextlib.contextmanager
def open_image(*, fp: IO[bytes]) -> Generator[Image.Image]:
    """Open an image however many pixels it has.

    Pillow raises :class:`PIL.Image.DecompressionBombError` when opening an
    image with more than twice ``Image.MAX_IMAGE_PIXELS`` pixels, and a small
    file can decode to many more pixels than that.
    Real Vuforia returns a response for such an image rather than failing to
    respond, so the mock must be able to open one.

    Pillow checks the pixel count when the image is opened, not when it is
    decoded, so ``Image.MAX_IMAGE_PIXELS`` is restored before the image is
    used.

    Args:
        fp: A file object with the content of the image.

    Yields:
        The opened image.
    """
    with _MAX_IMAGE_PIXELS_LOCK:
        original_max_image_pixels = Image.MAX_IMAGE_PIXELS
        Image.MAX_IMAGE_PIXELS = None
        try:
            image = Image.open(fp=fp)
        finally:
            Image.MAX_IMAGE_PIXELS = original_max_image_pixels

    with image:
        yield image
