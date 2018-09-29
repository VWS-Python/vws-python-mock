"""
Vuforia database states.
"""

from enum import Enum, auto


class States(Enum):
    """
    Constants representing various web service states.
    """

    WORKING = auto()

    # A project is inactive if the license key has been deleted.
    PROJECT_INACTIVE = auto()

    def __repr__(self) -> str:
        """
        Return a representation which does not include the generated number.
        """
        return '<{class_name}.{state_name}>'.format(
            class_name=self.__class__.__name__,
            state_name=self.name,
        )
