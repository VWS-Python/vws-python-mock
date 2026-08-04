"""Vuforia database states."""

from enum import StrEnum, auto, unique

from beartype import beartype


@beartype
@unique
class States(StrEnum):
    """Constants representing various web service states."""

    WORKING = auto()

    PROJECT_SUSPENDED = auto()

    # A project is inactive if the license key has been deleted.
    PROJECT_INACTIVE = auto()

    PROJECT_HAS_NO_API_ACCESS = auto()
