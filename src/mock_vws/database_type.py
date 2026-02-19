"""Vuforia database types."""

from enum import StrEnum, auto, unique

from beartype import beartype


@beartype
@unique
class DatabaseType(StrEnum):
    """Constants representing various database types."""

    CLOUD_RECO = auto()
    VUMARK = auto()
