"""Setup script for VWS Python Mock, a mock of Vuforia's Web Services APIs."""

from setuptools import setup

# We use requirements.txt instead of just declaring the requirements here
# because this helps with Docker package caching.
with open('requirements.txt') as requirements:
    INSTALL_REQUIRES = requirements.readlines()

# We use dev-requirements.txt instead of just declaring the requirements here
# because Read The Docs needs a requirements file.
with open('dev-requirements.txt') as dev_requirements:
    DEV_REQUIRES = dev_requirements.readlines()

setup(
    use_scm_version={
        'write_to': 'src/mock_vws/_setuptools_scm_version.txt',
    },
    setup_requires=['setuptools_scm', 'setuptools_scm_git_archive'],
    install_requires=INSTALL_REQUIRES,
    extras_require={'dev': DEV_REQUIRES},
)
