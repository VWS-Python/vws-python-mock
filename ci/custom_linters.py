"""
Custom lint tests.
"""

import subprocess
from pathlib import Path

import pytest
import yaml


def _ci_patterns() -> set[str]:
    """
    Return the CI patterns given in the CI configuration file.
    """
    repository_root = Path(__file__).parent.parent
    ci_file = repository_root / ".github" / "workflows" / "ci.yml"
    github_workflow_config = yaml.safe_load(ci_file.read_text())
    matrix = github_workflow_config["jobs"]["build"]["strategy"]["matrix"]
    ci_pattern_list = matrix["ci_pattern"]
    ci_patterns = set(ci_pattern_list)
    assert len(ci_pattern_list) == len(ci_patterns)
    return ci_patterns


def _tests_from_pattern(ci_pattern: str) -> set[str]:
    """
    From a CI pattern, get all tests ``pytest`` would collect.
    """
    tests: set[str] = set()
    args = ["pytest", "-q", "--collect-only", ci_pattern]
    result = subprocess.run(args=args, stdout=subprocess.PIPE, check=True)
    for line in result.stdout.decode().splitlines():
        if line and "collected in" not in line:
            tests.add(line)
    return tests


def test_ci_patterns_valid() -> None:
    """
    All of the CI patterns in the CI configuration match at least one test in
    the test suite.
    """
    ci_patterns = _ci_patterns()

    for ci_pattern in ci_patterns:
        pattern = "tests/mock_vws/" + ci_pattern
        collect_only_result = pytest.main(["--collect-only", pattern])

        message = f'"{ci_pattern}" does not match any tests.'
        assert collect_only_result == 0, message


def test_tests_collected_once() -> None:
    """
    Each test in the test suite is collected exactly once.

    This does not necessarily mean that they are run - they may be skipped.
    """
    ci_patterns = _ci_patterns()
    tests_to_patterns: dict[str, set[str]] = {}
    for pattern in ci_patterns:
        pattern_in_dir = "tests/mock_vws/" + pattern
        tests = _tests_from_pattern(ci_pattern=pattern_in_dir)
        for test in tests:
            if test in tests_to_patterns:
                tests_to_patterns[test].add(pattern_in_dir)
            else:
                tests_to_patterns[test] = {pattern_in_dir}

    for test_name, patterns in tests_to_patterns.items():
        message = (
            f'Test "{test_name}" will be run once for each pattern in '
            f"{patterns}. "
            "Each test should be run only once."
        )
        assert len(patterns) == 1, message

    all_tests = _tests_from_pattern(ci_pattern="tests/")
    assert tests_to_patterns.keys() - all_tests == set()
    assert all_tests - tests_to_patterns.keys() == set()
