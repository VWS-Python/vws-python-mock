"""Custom lint tests."""

from pathlib import Path

import pytest
import yaml
from beartype import beartype
from pytest_partition_check import PartitionError, check_partition

# Plugins which break nested ``pytest`` collection runs.
_DISABLED_PLUGINS = (
    # Disable pytest-retry to avoid:
    # ```
    # ValueError: no option named 'filtered_exceptions'
    # ```
    # which causes the nested run to exit with INTERNAL_ERROR
    # before any items are collected.
    "pytest-retry",
    # Disable pytest-beartype-tests to avoid
    # https://github.com/beartype/beartype/issues/637 — wrapping
    # collected items with @beartype installs a buggy
    # __annotate_beartype__ closure on the underlying test function,
    # which crashes a subsequent nested collection on Python 3.14.
    "pytest_beartype_tests",
)

# Disable warnings to avoid many instances of:
# ```
# Unknown config option: retry_delay
# ```
_EXTRA_ARGS = ("--disable-warnings",)


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


def test_ci_patterns_partition_test_suite(
    request: pytest.FixtureRequest,
) -> None:
    """The CI patterns partition the test suite.

    That is, every CI pattern matches at least one test, and every test
    is collected by exactly one CI pattern.

    A test being collected does not necessarily mean that it is run - it
    may be skipped.
    """
    repository_root = request.config.rootpath
    ci_patterns = _ci_patterns(repository_root=repository_root)

    try:
        check_partition(
            patterns=ci_patterns,
            rootdir=repository_root,
            disable_plugins=_DISABLED_PLUGINS,
            extra_args=_EXTRA_ARGS,
        )
    except PartitionError as exc:
        pytest.fail(reason=str(object=exc))
