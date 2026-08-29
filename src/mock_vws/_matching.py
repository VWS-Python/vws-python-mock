"""Tools for finding the targets which match an image."""

import operator
from collections.abc import Iterable

from beartype import beartype

from mock_vws._mock_common import sorted_targets
from mock_vws.image_matchers import ImageMatcher
from mock_vws.target import ImageTarget


@beartype
def _match_score(
    *,
    matcher: ImageMatcher,
    target_image_content: bytes,
    image_content: bytes,
) -> float | None:
    """The matcher's score for two images, or ``None`` for no match.

    Args:
        matcher: The matcher to score the images with.
        target_image_content: The content of a target's image.
        image_content: The content of the image to match against.

    Returns:
        The matcher's score, where a higher score is a better match, or
        ``None`` if the matcher says that the images do not match.

    Raises:
        TypeError: The matcher returned a ``bool``.  Matchers used to
            answer yes or no; they now return a score or ``None``.
    """
    score = matcher(
        first_image_content=target_image_content,
        second_image_content=image_content,
    )
    if isinstance(score, bool):
        message = (
            f"Image matchers must return a score or None, but "
            f"{matcher!r} returned {score!r}. A matcher which has no "
            f"score to give can return a constant score, such as 1.0, "
            f"for every match."
        )
        raise TypeError(message)
    if score is None:
        return None
    return float(score)


@beartype
def matching_targets(
    *,
    matcher: ImageMatcher,
    image_content: bytes,
    targets: Iterable[ImageTarget],
) -> list[ImageTarget]:
    """The given targets which match an image, best match first.

    Args:
        matcher: The matcher to decide which targets match, and how well.
        image_content: The content of the image to match against.
        targets: The targets to match, given as each target's image
            content is the matcher's first image.

    Returns:
        The targets which match, ordered by match score with the best match
        first.  Targets which the matcher gives the same score, as every
        match of a matcher with only a yes or no answer has, keep the
        deterministic upload date and then target ID order.
    """
    scored_targets: list[tuple[float, ImageTarget]] = []
    for target in sorted_targets(targets=targets):
        score = _match_score(
            matcher=matcher,
            target_image_content=target.image_value,
            image_content=image_content,
        )
        if score is not None:
            scored_targets.append((score, target))

    # ``sorted`` is stable, so targets with equal scores keep the order
    # which ``sorted_targets`` gave them.
    return [
        target
        for _, target in sorted(
            scored_targets,
            key=operator.itemgetter(0),
            reverse=True,
        )
    ]
