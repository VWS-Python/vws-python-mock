"""
Tools for using a fake implementation of Vuforia.
"""

from ._database import VuforiaDatabase
from ._decorators import MockVWS
from ._version import get_versions

__all__ = [
    'MockVWS',
    'VuforiaDatabase',
]

__version__ = get_versions()['version']  # type: ignore
del get_versions
