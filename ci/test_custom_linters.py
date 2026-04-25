"""Custom lint tests."""

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml
from beartype import beartype

if TYPE_CHECKING:
    from collections.abc import Iterable


@beartype
def _ci_patterns(*, repository_root: Path) -> set[str]:
    """Return the CI patterns given in the CI configuration file."""
    ci_file = repository_root / ".github" / "workflows" / "test.yml"
    github_workflow_config = yaml.safe_load(stream=ci_file.read_text())
    matrix = github_workflow_config["jobs"]["ci-tests"]["strategy"]["matrix"]
    ci_pattern_list = matrix["ci_pattern"]
    ci_patterns = set(ci_pattern_list)
    assert len(ci_pattern_list) == len(ci_patterns)
    return ci_patterns


@beartype
def _collect(
    *, ci_pattern: str, repository_root: Path
) -> subprocess.CompletedProcess[str]:
    """Run ``pytest --collect-only`` for ``ci_pattern`` in a fresh
    subprocess.

    A real subprocess (not ``pytest.main``) is used so that plugin state
    (notably ``pytest-beartype-tests`` re-wrapping the same test
    functions) does not accumulate across iterations and trigger
    ``Cannot stringify annotation containing string formatting`` under
    Python 3.14 deferred annotations.
    """
    return subprocess.run(
        args=[
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--collect-only",
            "--disable-warnings",
            ci_pattern,
        ],
        check=False,
        cwd=repository_root,
        capture_output=True,
        text=True,
    )


def test_ci_patterns_valid(request: pytest.FixtureRequest) -> None:
    """
    All of the CI patterns in the CI configuration match at least one
    test in
    the test suite.
    """
    repository_root = request.config.rootpath
    ci_patterns = _ci_patterns(repository_root=repository_root)

    for ci_pattern in ci_patterns:
        result = _collect(
            ci_pattern=ci_pattern,
            repository_root=repository_root,
        )
        message = (
            f'"{ci_pattern}" does not match any tests.\n'
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert result.returncode == 0, message


def test_tests_collected_once(
    *,
    request: pytest.FixtureRequest,
) -> None:
    """Each test in the test suite is collected exactly once.

    This does not necessarily mean that they are run - they may be skipped.
    """
    repository_root = request.config.rootpath
    ci_patterns = _ci_patterns(repository_root=repository_root)
    tests_to_patterns: dict[str, set[str]] = {}

    for pattern in ci_patterns:
        tests = _tests_from_pattern(
            ci_pattern=pattern,
            repository_root=repository_root,
        )
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

    all_tests = _tests_from_pattern(
        ci_pattern=".",
        repository_root=repository_root,
    )
    # Exclude this file's own meta-tests from the comparison: they are
    # not part of any CI pattern by design (they validate the patterns).
    all_tests = {t for t in all_tests if not t.startswith("ci/")}
    assert tests_to_patterns.keys() - all_tests == set()
    assert all_tests - tests_to_patterns.keys() == set()


@beartype
def _tests_from_pattern(
    *,
    ci_pattern: str,
    repository_root: Path,
) -> set[str]:
    """From a CI pattern, get all tests ``pytest`` would collect."""
    result = _collect(
        ci_pattern=ci_pattern,
        repository_root=repository_root,
    )
    tests: Iterable[str] = set()
    for line in result.stdout.splitlines():
        # We filter empty lines and lines which look like
        # "9 tests collected in 0.01s".
        if line and "collected in" not in line:
            tests = {*tests, line}
    return set(tests)
