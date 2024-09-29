"""
Vuforia database states.
"""

from enum import StrEnum, auto

from beartype import beartype


@beartype
class States(StrEnum):
    """
    Constants representing various web service states.
    """

    WORKING = auto()

    # A project is inactive if the license key has been deleted.
    PROJECT_INACTIVE = auto()
