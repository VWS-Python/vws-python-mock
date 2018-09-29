"""
Tools for using a fake implementation of Vuforia.
"""

from ._constants import States
from ._database import VuforiaDatabase
from ._decorators import MockVWS
from ._version import get_versions

__all__ = [
    'MockVWS',
    'States',
    'VuforiaDatabase',
]

__version__ = get_versions()['version']  # type: ignore
del get_versions
