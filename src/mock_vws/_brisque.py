"""Wrapper around the brisque package for image quality scoring."""

from __future__ import annotations

import io

import numpy as np
from brisque import (  # type: ignore[attr-defined]  # pyright: ignore[reportMissingTypeStubs]
    BRISQUE,
)
from PIL import Image

_brisque_scorer = BRISQUE(url=False)  # type: ignore[no-untyped-call]


def brisque_score(image_content: bytes) -> float:
    """Return a BRISQUE quality score for the given image bytes."""
    image_file = io.BytesIO(initial_bytes=image_content)
    image = Image.open(fp=image_file).convert(mode="RGB")
    image_np: np.ndarray = np.array(object=image)
    return float(
        _brisque_scorer.score(img=image_np)  # type: ignore[no-untyped-call]  # pyright: ignore[reportUnknownMemberType]
    )
