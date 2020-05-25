"""
Move the right secrets file into place for Travis CI.
"""

import os
import shutil
from pathlib import Path
import sys


def move_secrets_file() -> None:
    """
    Move the right secrets file to the current directory.
    """
    # TODO change this
    from pprint import pprint
    print(dict(os.environ))
    sys.exit(0)
    travis_job_number = 1  # os.environ['TRAVIS_JOB_NUMBER']
    travis_builder_number = travis_job_number.split('.')[-1]
    secrets_dir = Path('ci_secrets')
    secrets_path = secrets_dir / f'vuforia_secrets_{travis_builder_number}.env'
    shutil.copy(secrets_path, './vuforia_secrets.env')
    # TODO this is temporary


if __name__ == '__main__':
    move_secrets_file()
