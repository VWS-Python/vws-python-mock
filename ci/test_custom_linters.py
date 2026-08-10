"""Custom lint tests."""

import ast
from pathlib import Path

import pytest
import yaml
from beartype import beartype


def test_pre_commit_hook_identifiers_unique(
    request: pytest.FixtureRequest,
) -> None:
    """Each pre-commit hook has a unique ID and display name."""
    config_file = request.config.rootpath / ".pre-commit-config.yaml"
    config = yaml.safe_load(stream=config_file.read_text())
    hooks = [
        hook
        for repository in config["repos"]
        for hook in repository.get("hooks", [])
    ]
    hook_ids = [hook["id"] for hook in hooks]
    hook_names = [hook.get("name", hook["id"]) for hook in hooks]

    assert len(hook_ids) == len(set(hook_ids)), (
        "Pre-commit hook IDs must be unique."
    )
    assert len(hook_names) == len(set(hook_names)), (
        "Pre-commit hook names must be unique."
    )


def test_validate_and_run_functions_are_keyword_only(
    request: pytest.FixtureRequest,
) -> None:
    """Validation and runner APIs do not accept positional arguments."""
    violations: list[str] = []
    source_root = request.config.rootpath / "src"

    for source_file in source_root.rglob("*.py"):
        module = ast.parse(source_file.read_text())
        for function in ast.walk(module):
            if not isinstance(
                function, ast.FunctionDef | ast.AsyncFunctionDef
            ):
                continue
            if not function.name.startswith(("validate_", "run_")):
                continue
            positional_arguments = [
                argument.arg
                for argument in [
                    *function.args.posonlyargs,
                    *function.args.args,
                ]
                if argument.arg not in {"self", "cls"}
            ]
            if positional_arguments:
                path = source_file.relative_to(request.config.rootpath)
                violations.append(f"{path}:{function.lineno} {function.name}")

    assert not violations, "Functions must be keyword-only: " + ", ".join(
        violations
    )


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
    """Pytest plugin that records the node IDs of collected items."""

    def __init__(self) -> None:
        """Start with an empty set of collected node IDs."""
        self.collected: set[str] = set()

    def pytest_itemcollected(self, item: pytest.Item) -> None:
        """Record each collected item's node ID."""
        self.collected.add(item.nodeid)


@beartype
def _tests_from_pattern(*, ci_pattern: str) -> set[str]:
    """From a CI pattern, get all tests ``pytest`` would collect."""
    plugin = _CollectPlugin()
    pytest.main(
        args=[
            "-q",
            "--collect-only",
            # Disable pytest-retry to avoid:
            # ```
            # ValueError: no option named 'filtered_exceptions'
            # ```
            # which causes the nested run to exit with INTERNAL_ERROR
            # before any items are collected.
            "-p",
            "no:pytest-retry",
            # Disable pytest-beartype-tests to avoid
            # https://github.com/beartype/beartype/issues/637 — wrapping
            # collected items with @beartype installs a buggy
            # __annotate_beartype__ closure on the underlying test
            # function, which crashes a subsequent nested collection on
            # Python 3.14.
            "-p",
            "no:pytest_beartype_tests",
            # Disable warnings to avoid many instances of:
            # ```
            # Unknown config option: retry_delay
            # ```
            "--disable-warnings",
            ci_pattern,
        ],
        plugins=[plugin],
    )
    return plugin.collected


def test_ci_patterns_valid(request: pytest.FixtureRequest) -> None:
    """
    All of the CI patterns in the CI configuration match at least one
    test in
    the test suite.
    """
    ci_patterns = _ci_patterns(repository_root=request.config.rootpath)

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
                # Disable pytest-beartype-tests to avoid
                # https://github.com/beartype/beartype/issues/637 —
                # wrapping collected items with @beartype installs a
                # buggy __annotate_beartype__ closure on the underlying
                # test function, which crashes a subsequent nested
                # collection on Python 3.14.
                "-p",
                "no:pytest_beartype_tests",
                # Disable warnings to avoid many instances of:
                # ```
                # Unknown config option: retry_delay
                # ```
                "--disable-warnings",
            ],
        )

        message = f'"{ci_pattern}" does not match any tests.'
        assert collect_only_result == 0, message


def test_tests_collected_once(request: pytest.FixtureRequest) -> None:
    """Each test in the test suite is collected exactly once.

    This does not necessarily mean that they are run - they may be skipped.
    """
    ci_patterns = _ci_patterns(repository_root=request.config.rootpath)
    all_tests = _tests_from_pattern(ci_pattern=".")
    assert all_tests
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

    assert tests_to_patterns.keys() - all_tests == set()
    assert all_tests - tests_to_patterns.keys() == set()
