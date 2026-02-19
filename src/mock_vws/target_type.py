"""Vuforia target types."""

from enum import StrEnum, auto, unique

from beartype import beartype


@beartype
@unique
class TargetType(StrEnum):
    """Constants representing various target types."""

    IMAGE = auto()
    VUMARK_TEMPLATE = auto()
