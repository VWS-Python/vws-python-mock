"""Convert BRISQUE scores to Vuforia tracking ratings."""

import math

from beartype import beartype


@beartype
def rating_from_brisque_score(*, brisque_score: float) -> int:
    """Convert a quality score to a tracking rating between zero and five.

    Undefined scores have the lowest tracking rating.
    """
    if not math.isfinite(brisque_score):
        return 0

    # BRISQUE ranges from 0 (best) to 100 (worst), while Vuforia's target
    # tracking rating ranges from 0 (worst) to 5 (best).
    rating = 5 - math.floor(brisque_score / 20)
    return min(5, max(0, rating))
