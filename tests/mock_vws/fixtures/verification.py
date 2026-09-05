"""Enforce and report which tests verify the mock against real Vuforia.

This plugin is the mechanism which the declarations in
:mod:`tests.mock_vws.verification` feed.  It refuses to run a suite in
which a test which never reaches real Vuforia does not say why, it
reports the verified and unverified split of whatever was collected, and
it counts the tests which stopped verifying anything while they ran.
"""

import json
from collections import Counter
from pathlib import Path

import pytest
from beartype import beartype

from tests.mock_vws.fixtures.vuforia_backends import VuforiaBackend
from tests.mock_vws.verification import (
    RUNTIME_UNVERIFIED,
    UnverifiedReason,
    VuforiaAPI,
    api_for_test_path,
    group_by_test,
    is_test_function,
    is_verified,
    marker_detail,
    marker_reason,
    mock_only_marker,
)

_VERIFICATION_REPORT_OPTION = "--verification-report"

# The split of the collected tests, from collection to the summary.
_SPLIT_KEY = pytest.StashKey[dict[str, Counter[str]]]()

_VERIFIED = "verified"

_MISSING_MARKER_MESSAGE = """\
These tests never run against the real Vuforia, and do not say why:

{tests}

A test which runs against the mocks only verifies that the mock matches
itself.  Declare which of the reasons in
``tests.mock_vws.verification.UnverifiedReason`` applies, on the test or
on its class:

    from tests.mock_vws.verification import UnverifiedReason, mock_only

    @mock_only(
        reason=UnverifiedReason.INHERENTLY_UNVERIFIABLE,
        detail="Why real Vuforia cannot be asked this.",
    )

If instead the test should reach real Vuforia, give it the
``verify_mock_vuforia`` or ``verify_model_target_mock_vuforia`` fixture.
"""


@beartype
def pytest_addoption(parser: pytest.Parser) -> None:
    """Add options for reporting the verified and unverified split."""
    group = parser.getgroup(name="verification")
    group.addoption(
        _VERIFICATION_REPORT_OPTION,
        action="store",
        default=None,
        help=(
            "Write the verified and unverified split of the collected "
            "tests, and any tests which stopped verifying anything while "
            "they ran, to this path as JSON."
        ),
    )
    group.addoption(
        "--fail-on-runtime-unverified",
        action="store_true",
        default=False,
        help=(
            "Exit non-zero if any test stopped verifying anything while it "
            "ran, such as a Model Target test which the account's training "
            "allowance rejected."
        ),
    )


@beartype
def _split(*, items: list[pytest.Item]) -> dict[str, Counter[str]]:
    """The verified and unverified split of collected tests, per API.

    Args:
        items: The collected items.

    Returns:
        The number of verified tests, and of unverified tests of each
        reason, for each API which has collected tests.

    Raises:
        UsageError: A test which never runs against real Vuforia does
            not declare why.
    """
    split: dict[str, Counter[str]] = {}
    missing: list[str] = []
    real_backend_id = str(object=VuforiaBackend.REAL.value)
    test_functions = [item for item in items if is_test_function(item=item)]
    for test_id, test_items in group_by_test(items=test_functions).items():
        first_item = test_items[0]
        api = api_for_test_path(path=first_item.path)
        counts = split.setdefault(api.value, Counter())
        marker = mock_only_marker(item=first_item)
        if marker is None:
            if is_verified(
                items=test_items,
                real_backend_id=real_backend_id,
            ):
                counts[_VERIFIED] += 1
            else:
                missing.append(test_id)
            continue

        counts[marker_reason(mark=marker).value] += 1
        # A marked test which is parametrized over the real Vuforia does
        # not run against it.  Skipping those items here, rather than in
        # the test, is what keeps the declaration and the behavior the
        # same thing.
        skip_real = pytest.mark.skip(reason=marker_detail(mark=marker))
        for item in test_items:
            if real_backend_id in str.partition(item.nodeid, "[")[2]:
                item.add_marker(marker=skip_real)

    if missing:
        raise pytest.UsageError(
            _MISSING_MARKER_MESSAGE.format(
                tests="\n".join(f"    {test}" for test in missing),
            ),
        )

    return split


@beartype
def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Check that every collected test says what it verifies."""
    config.stash[_SPLIT_KEY] = _split(items=items)


@beartype
def _split_lines(*, split: dict[str, Counter[str]]) -> list[str]:
    """The verified and unverified split, one line per API.

    Args:
        split: The split to describe.

    Returns:
        A line for each API with collected tests, and one total line.
    """
    totals: Counter[str] = Counter()
    lines: list[str] = []
    for api in VuforiaAPI:
        counts = split.get(api.value)
        if counts is None:
            continue
        totals += counts
        lines.append(f"{api.value}: {_counts_description(counts=counts)}")
    lines.append(f"All collected tests: {_counts_description(counts=totals)}")
    return lines


@beartype
def _counts_description(*, counts: Counter[str]) -> str:
    """A description of the counts of one API.

    Args:
        counts: The counts to describe.

    Returns:
        The counts, verified first.
    """
    unverified = [
        f"{reason.value} {counts[reason.value]}"
        for reason in UnverifiedReason
        if counts[reason.value]
    ]
    return ", ".join([f"verified {counts[_VERIFIED]}", *unverified])


@beartype
def _runtime_unverified_lines() -> list[str]:
    """The tests which stopped verifying anything while they ran.

    Returns:
        A line for each such test, or an empty list if there were none.
    """
    return [
        f"{node_id}: {reason.value}: {detail.splitlines()[0]}"
        for node_id, reason, detail in RUNTIME_UNVERIFIED
    ]


@beartype
def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter,
    config: pytest.Config,
) -> None:
    """Report the split, and any test which stopped verifying anything."""
    empty_split: dict[str, Counter[str]] = {}
    split = config.stash.get(key=_SPLIT_KEY, default=empty_split)
    terminalreporter.write_sep(sep="=", title="verification split")
    for line in _split_lines(split=split):
        terminalreporter.write_line(line=line)

    runtime_lines = _runtime_unverified_lines()
    if runtime_lines:
        terminalreporter.write_sep(
            sep="=",
            title="stopped verifying anything while running",
            red=True,
        )
        for line in runtime_lines:
            terminalreporter.write_line(line=line)

    report_path = config.getoption(name=_VERIFICATION_REPORT_OPTION)
    if report_path is not None:
        Path(str(object=report_path)).write_text(
            data=json.dumps(
                obj={
                    "split": {
                        api: dict(counts) for api, counts in split.items()
                    },
                    "runtime_unverified": [
                        {
                            "test": node_id,
                            "reason": reason.value,
                            "detail": detail,
                        }
                        for node_id, reason, detail in RUNTIME_UNVERIFIED
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


@beartype
def pytest_sessionfinish(session: pytest.Session) -> None:
    """Fail a run in which a test stopped verifying anything, if asked."""
    fail = session.config.getoption(name="--fail-on-runtime-unverified")
    if fail and RUNTIME_UNVERIFIED:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
