"""
Custom lint tests.
"""

import subprocess
from pathlib import Path
from typing import Dict, Set

import pytest
import yaml


def _ci_patterns() -> Set[str]:
    """
    Return the CI patterns given in the CI configuration file.
    """
    repository_root = Path(__file__).parent.parent
    ci_file = repository_root / '.github' / 'workflows' / 'ci.yml'
    github_workflow_config = yaml.safe_load(ci_file.read_text())
    matrix = github_workflow_config['jobs']['build']['strategy']['matrix']
    ci_pattern_list = matrix['ci_pattern']
    ci_patterns = set(ci_pattern_list)
    assert len(ci_pattern_list) == len(ci_patterns)
    return ci_patterns


def _tests_from_pattern(ci_pattern: str) -> Set[str]:
    """
    From a CI pattern, get all tests ``pytest`` would collect.
    """
    tests: Set[str] = set([])
    args = ['pytest', '-p', 'no:terminal', '--collect-only', ci_pattern]
    result = subprocess.run(args=args, stdout=subprocess.PIPE, check=True)
    tests = set(result.stdout.decode().splitlines())
    return tests


def test_ci_patterns_valid() -> None:
    """
    All of the CI patterns in the CI configuration match at least one test in
    the test suite.
    """
    ci_patterns = _ci_patterns()

    for ci_pattern in ci_patterns:
        pattern = 'tests/mock_vws/' + ci_pattern
        collect_only_result = pytest.main(['--collect-only', pattern])

        message = f'"{ci_pattern}" does not match any tests.'
        assert collect_only_result == 0, message


def test_tests_collected_once() -> None:
    """
    Each test in the test suite is collected exactly once.

    This does not necessarily mean that they are run - they may be skipped.
    """
    ci_patterns = _ci_patterns()
    tests_to_patterns: Dict[str, Set[str]] = {}
    for pattern in ci_patterns:
        pattern = 'tests/mock_vws/' + pattern
        tests = _tests_from_pattern(ci_pattern=pattern)
        for test in tests:
            if test in tests_to_patterns:
                tests_to_patterns[test].add(pattern)
            else:
                tests_to_patterns[test] = set([pattern])

    for test_name, patterns in tests_to_patterns.items():
        message = (
            f'Test "{test_name}" will be run once for each pattern in '
            f'{patterns}. '
            'Each test should be run only once.'
        )
        assert len(patterns) == 1, message

    all_tests = _tests_from_pattern(ci_pattern='tests/')
    assert tests_to_patterns.keys() - all_tests == set()
    assert all_tests - tests_to_patterns.keys() == set()


def test_init_files() -> None:
    """
    ``__init__`` files exist where they should do.

    If ``__init__`` files are missing, linters may not run on all files that
    they should run on.
    """
    directories = (Path('src'), Path('tests'))

    for directory in directories:
        files = directory.glob('**/*.py')
        for python_file in files:
            parent = python_file.parent
            expected_init = parent / '__init__.py'
            assert expected_init.exists()
