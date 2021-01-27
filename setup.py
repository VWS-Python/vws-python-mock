"""
Setup script for VWS Python Mock, a mock of Vuforia's Web Services APIs.
"""

from __future__ import annotations

from pathlib import Path

from setuptools import setup


def _get_dependencies(requirements_file: Path) -> list[str]:
    """
    Return requirements from a requirements file.

    This expects a requirements file with no ``--find-links`` lines.
    """
    lines = requirements_file.read_text().strip().split('\n')
    return [line for line in lines if not line.startswith('#')]


INSTALL_REQUIRES = _get_dependencies(
    requirements_file=Path('requirements.txt'),
)

DEV_REQUIRES = _get_dependencies(
    requirements_file=Path('dev-requirements.txt'),
)

SETUP_REQUIRES = _get_dependencies(
    requirements_file=Path('setup-requirements.txt'),
)

setup(
    # We use a dictionary with a fallback version rather than "True"
    # like https://github.com/pypa/setuptools_scm/issues/77 so that we do not
    # error in Docker.
    use_scm_version={'fallback_version': 'FALLBACK_VERSION'},
    setup_requires=SETUP_REQUIRES,
    install_requires=INSTALL_REQUIRES,
    extras_require={'dev': DEV_REQUIRES},
)
