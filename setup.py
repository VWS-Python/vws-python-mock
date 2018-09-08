"""Setup script for VWS Python Mock, a mock of Vuforia's Web Services APIs."""

from setuptools import find_packages, setup

import versioneer

# We use requirements.txt instead of just declaring the requirements here
# because this helps with Docker package caching.
with open('requirements.txt') as requirements:
    INSTALL_REQUIRES = requirements.readlines()

# We use dev-requirements.txt instead of just declaring the requirements here
# because Read The Docs needs a requirements file.
with open('dev-requirements.txt') as dev_requirements:
    DEV_REQUIRES = dev_requirements.readlines()

with open('README.rst') as f:
    LONG_DESCRIPTION = f.read()

setup(
    name='VWS Python Mock',
    version=versioneer.get_version(),  # type: ignore
    cmdclass=versioneer.get_cmdclass(),  # type: ignore
    author='Adam Dangoor',
    author_email='adamdangoor@gmail.com',
    description='A mock for the Vuforia Web Services (VWS) API.',
    long_description=LONG_DESCRIPTION,
    license='MIT',
    packages=find_packages(where='src'),
    zip_safe=False,
    url='http://vws-python-mock.readthedocs.io',
    keywords='vuforia mock fake client',
    package_dir={'': 'src'},
    install_requires=INSTALL_REQUIRES,
    extras_require={
        'dev': DEV_REQUIRES,
    },
    include_package_data=True,
    classifiers=[
        'Operating System :: POSIX',
        'Environment :: Web Environment',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
)
