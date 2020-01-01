"""
Tools for using a fake implementation of Vuforia.
"""

from pathlib import Path

from setuptools_scm import get_version

from ._decorators import MockVWS

__all__ = [
    'MockVWS',
]
