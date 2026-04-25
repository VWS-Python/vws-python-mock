"""Custom lint tests."""

from pathlib import Path

import pytest
import yaml
from beartype import beartype


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


class _CollectPlugin:
    """Pytest plugin that records collected node IDs."""

    def __init__(self) -> None:
        """Initialize an empty set of collected node IDs."""
        self.nodeids: set[str] = set()

    def pytest_collection_modifyitems(
        self,
        items: list[pytest.Item],
    ) -> None:
        """Record the node IDs of all collected items."""
        self.nodeids.update(item.nodeid for item in items)


@beartype
def _tests_from_pattern(*, ci_pattern: str) -> set[str]:
    """From a CI pattern, get all tests ``pytest`` would collect.

    Uses a collection-hook plugin instead of parsing stdout: an in-process
    ``pytest.main()`` installs its own output capture, so reading from
    ``capsys`` would see an empty string and the test would pass vacuously.
    """
    plugin = _CollectPlugin()
    exit_code = pytest.main(
        args=[
            "--collect-only",
            # Disable pytest-retry to avoid:
            # ```
            # ValueError: no option named 'filtered_exceptions'
            # ```
            "-p",
            "no:pytest-retry",
            # Disable warnings to avoid many instances of:
            # ```
            # Unknown config option: retry_delay
            # ```
            "--disable-warnings",
            ci_pattern,
        ],
        plugins=[plugin],
    )
    # Fail loudly on collection errors (import failures, syntax errors, etc.)
    # rather than silently using whatever items were captured before the
    # crash.
    assert exit_code == pytest.ExitCode.OK, (
        f"Collection for {ci_pattern!r} failed with exit code {exit_code}."
    )
    return plugin.nodeids


def test_ci_patterns_valid(request: pytest.FixtureRequest) -> None:
    """
    All of the CI patterns in the CI configuration match at least one
    test in
    the test suite.
    """
    ci_patterns = _ci_patterns(repository_root=request.config.rootpath)

    for ci_pattern in ci_patterns:
        tests = _tests_from_pattern(ci_pattern=ci_pattern)
        message = f'"{ci_pattern}" does not match any tests.'
        assert tests, message


def test_tests_collected_once(
    *,
    request: pytest.FixtureRequest,
) -> None:
    """Each test in the test suite is collected exactly once.

    This does not necessarily mean that they are run - they may be skipped.
    """
    ci_patterns = _ci_patterns(repository_root=request.config.rootpath)
    tests_to_patterns: dict[str, set[str]] = {}

    for pattern in ci_patterns:
        tests = _tests_from_pattern(ci_pattern=pattern)
        for test in tests:
            tests_to_patterns.setdefault(test, set()).add(pattern)

    for test_name, patterns in tests_to_patterns.items():
        message = (
            f'Test "{test_name}" will be run once for each pattern in '
            f"{patterns}. "
            "Each test should be run only once."
        )
        assert len(patterns) == 1, message

    all_tests = _tests_from_pattern(ci_pattern=".")
    assert tests_to_patterns.keys() - all_tests == set()
    assert all_tests - tests_to_patterns.keys() == set()
