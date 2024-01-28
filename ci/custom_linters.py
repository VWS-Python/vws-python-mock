"""
Custom lint tests.
"""

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


def _tests_from_pattern(
    ci_pattern: str,
    capsys: pytest.CaptureFixture[str],
) -> set[str]:
    """
    From a CI pattern, get all tests ``pytest`` would collect.
    """
    # Clear the captured output.
    capsys.readouterr()
    tests: set[str] = set()
    pytest.main(
        args=[
            "-q",
            "--collect-only",
            # If there are any warnings, these obscure the output.
            "--disable-warnings",
            ci_pattern,
        ],
    )
    data = capsys.readouterr().out
    for line in data.splitlines():
        # We filter empty lines and lines which look like
        # "9 tests collected in 0.01s".
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
        collect_only_result = pytest.main(
            args=[
                "--collect-only",
                ci_pattern,
                # Disable pytest-retry to avoid:
                # ```
                # ValueError: no option named 'filtered_exceptions'
                # ````
                "-p",
                "no:pytest-retry",
                # Disable warnings to avoid many instances of:
                # ```
                # Unknown config option: retry_delay
                # ```
                "--disable-warnings",
            ],
        )

        message = f'"{ci_pattern}" does not match any tests.'
        assert collect_only_result == 0, message


def test_tests_collected_once(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    Each test in the test suite is collected exactly once.

    This does not necessarily mean that they are run - they may be skipped.
    """
    ci_patterns = _ci_patterns()
    tests_to_patterns: dict[str, set[str]] = {}

    for pattern in ci_patterns:
        tests = _tests_from_pattern(ci_pattern=pattern, capsys=capsys)
        for test in tests:
            if test in tests_to_patterns:
                tests_to_patterns[test].add(pattern)
            else:
                tests_to_patterns[test] = {pattern}

    for test_name, patterns in tests_to_patterns.items():
        message = (
            f'Test "{test_name}" will be run once for each pattern in '
            f"{patterns}. "
            "Each test should be run only once."
        )
        assert len(patterns) == 1, message

    all_tests = _tests_from_pattern(ci_pattern=".", capsys=capsys)
    assert tests_to_patterns.keys() - all_tests == set()
    assert all_tests - tests_to_patterns.keys() == set()
