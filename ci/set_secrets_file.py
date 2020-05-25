"""
Move the right secrets file into place for CI.
"""

import os
import shutil
from pathlib import Path

import yaml


def move_secrets_file() -> None:
    """
    Move the right secrets file to the current directory.
    """
    repository_root = Path(__file__).parent.parent
    ci_file = repository_root / '.github' / 'workflows' / 'ci.yml'
    github_workflow_config = yaml.safe_load(ci_file.read_text())
    matrix = github_workflow_config['jobs']['build']['strategy']['matrix']
    ci_pattern_list = matrix['ci_pattern']
    current_ci_pattern = os.environ['CI_PATTERN']
    builder_number = ci_pattern_list.index(current_ci_pattern) + 1

    secrets_dir = Path('ci_secrets')
    secrets_path = secrets_dir / f'vuforia_secrets_{builder_number}.env'
    shutil.copy(secrets_path, './vuforia_secrets.env')


if __name__ == '__main__':
    move_secrets_file()
