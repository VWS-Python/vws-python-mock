"""Say which claims about real Vuforia each test verifies.

A test which runs against the real Vuforia checks that the mock matches
the service.  A test which runs against the mocks only checks that the
mock matches whatever the mock was written to do.  Both pass, both count
towards coverage, and both read like verification, so the difference has
to be written down rather than inferred.

Every test which never runs against the real Vuforia declares why with
:func:`mock_only`.  :mod:`tests.mock_vws.fixtures.verification` refuses
to run a suite in which one does not, and
``admin/verification_report.py`` turns the declarations into the
verified/unverified split recorded in ``verification.toml``.
"""

import os
from collections.abc import Mapping
from enum import Enum, unique
from pathlib import Path
from typing import NoReturn

import pytest
from beartype import beartype

# The name of the marker which says that a test never runs against the
# real Vuforia.  Registered in ``pyproject.toml``.
MOCK_ONLY_MARKER_NAME = "mock_only"


@unique
class UnverifiedReason(Enum):
    """Why a claim which the mock makes has not been observed from real
    Vuforia.
    """

    TEMPORARILY_UNVERIFIABLE = "temporarily-unverifiable"
    """The behavior is observable in principle, but not right now.

    The credentials, the account scope or the account allowance needed to
    provoke it are missing.  This one is expected to become verified, so
    it is the one to look at first.
    """

    INHERENTLY_UNVERIFIABLE = "inherently-unverifiable"
    """The behavior cannot be provoked against real Vuforia at all.

    A VuMark target held in ``PROCESSING``, a report caught mid
    generation, a configured generation failure.  These are mock-only
    forever.
    """

    NEVER_ATTEMPTED = "never-attempted"
    """The mock implements something from Vuforia's public documentation
    and nobody has checked that the documentation is accurate.

    This is the category which bites: the mock looks verified, and the
    divergence appears in production.
    """

    NO_VUFORIA_CLAIM = "no-vuforia-claim"
    """The test makes no claim about real Vuforia.

    It exercises the mock's own configuration API, its target manager,
    its container, or a test helper.  There is nothing for real Vuforia
    to agree or disagree with, so this category is not a debt.
    """


@unique
class VuforiaAPI(Enum):
    """An API which this project mocks, for reporting the split by."""

    TARGET = "VWS Target API"
    QUERY = "Vuforia Query API"
    VUMARK = "VuMark Instance Generation API"
    MODEL_TARGET = "Model Target Web API"
    RECO_COUNTS = "Reco Counts Report API"
    CROSS_CUTTING = "Cross-cutting request handling"
    MOCK_TOOLING = "Mock tooling"


# The API which each test module exercises.
#
# A module which is not named here is an error rather than a default, so
# that a new test module is classified deliberately.
_API_BY_MODULE: Mapping[str, VuforiaAPI] = {
    "test_add_target": VuforiaAPI.TARGET,
    "test_authorization_header": VuforiaAPI.CROSS_CUTTING,
    "test_cloud_query_failure_response": VuforiaAPI.QUERY,
    "test_content_length": VuforiaAPI.CROSS_CUTTING,
    "test_database_summary": VuforiaAPI.TARGET,
    "test_date_header": VuforiaAPI.CROSS_CUTTING,
    "test_delete_target": VuforiaAPI.TARGET,
    "test_docker": VuforiaAPI.MOCK_TOOLING,
    "test_flask_app_usage": VuforiaAPI.MOCK_TOOLING,
    "test_get_duplicates": VuforiaAPI.TARGET,
    "test_get_target": VuforiaAPI.TARGET,
    "test_healthcheck": VuforiaAPI.MOCK_TOOLING,
    "test_httpx2_mock_usage": VuforiaAPI.MOCK_TOOLING,
    "test_invalid_given_id": VuforiaAPI.TARGET,
    "test_invalid_json": VuforiaAPI.CROSS_CUTTING,
    "test_model_target_failure_response": VuforiaAPI.MODEL_TARGET,
    "test_model_target_generation_failure": VuforiaAPI.MODEL_TARGET,
    "test_model_target_generation_warning": VuforiaAPI.MODEL_TARGET,
    "test_model_target_retries": VuforiaAPI.MODEL_TARGET,
    "test_model_target_training_allowance": VuforiaAPI.MODEL_TARGET,
    "test_model_target_web_api": VuforiaAPI.MODEL_TARGET,
    "test_query": VuforiaAPI.QUERY,
    "test_reco_counts_report": VuforiaAPI.RECO_COUNTS,
    "test_requests_mock_usage": VuforiaAPI.MOCK_TOOLING,
    "test_respx_mock_usage": VuforiaAPI.MOCK_TOOLING,
    "test_target_list": VuforiaAPI.TARGET,
    "test_target_raters": VuforiaAPI.MOCK_TOOLING,
    "test_target_summary": VuforiaAPI.TARGET,
    "test_target_validators": VuforiaAPI.MOCK_TOOLING,
    "test_unexpected_json": VuforiaAPI.CROSS_CUTTING,
    "test_update_target": VuforiaAPI.TARGET,
    "test_verification": VuforiaAPI.MOCK_TOOLING,
    "test_vumark_generation_api": VuforiaAPI.VUMARK,
    "test_vumark_generation_failure": VuforiaAPI.VUMARK,
}


@beartype
def api_for_test_path(*, path: Path) -> VuforiaAPI:
    """The API which the tests in a module exercise.

    Args:
        path: The path of the test module.

    Returns:
        The API which the module exercises.

    Raises:
        KeyError: The module is not classified. Add it to
            ``_API_BY_MODULE``.
    """
    module_name = path.stem
    try:
        return _API_BY_MODULE[module_name]
    except KeyError:
        message = (
            f"{module_name} is not listed in the API mapping in "
            f"{Path(__file__).name}. Add it, so that the verified and "
            "unverified split reports its tests."
        )
        raise KeyError(message) from None


@beartype
def mock_only(
    *,
    reason: UnverifiedReason,
    detail: str,
) -> pytest.MarkDecorator:
    """Mark a test, or a class of tests, as never run against real
    Vuforia.

    Args:
        reason: Which kind of unverified this is.
        detail: What would have to change for the test to run against
            real Vuforia, or why nothing can.

    Returns:
        The marker to apply.
    """
    return pytest.mark.mock_only(reason=reason, detail=detail)


# Tests which were downgraded from verified to unverified while they ran,
# rather than at collection time.
#
# This is a list so that the plugin can drain it without a ``global``
# statement.
RUNTIME_UNVERIFIED: list[tuple[str, UnverifiedReason, str]] = []


@beartype
def unverified_at_runtime(
    *,
    reason: UnverifiedReason,
    detail: str,
) -> NoReturn:
    """Stop a test which cannot verify what it was written to verify.

    ``pytest.xfail`` is the only way to end a test which has found that
    the service, rather than the code under test, is at fault. It is also
    silent: ``xfail_strict`` does not apply to it, so however many tests
    stop verifying anything, the run stays green and nothing counts them.
    Recording the test here is what makes the count visible, in the
    terminal summary and in the report which
    :mod:`tests.mock_vws.fixtures.verification` writes.

    Args:
        reason: Which kind of unverified this is.
        detail: Why the test could not verify its claim, shown as the
            expected failure reason.

    Raises:
        Exception: Always, as an expected failure.
    """
    current_test = os.environ.get(
        key="PYTEST_CURRENT_TEST",
        default="unknown test",
    )
    RUNTIME_UNVERIFIED.append(
        (str.partition(current_test, " (")[0], reason, detail)
    )
    pytest.xfail(reason=detail)


@beartype
def mock_only_marker(*, item: pytest.Item) -> pytest.Mark | None:
    """The ``mock_only`` marker which applies to a test, if any.

    Args:
        item: The test to look at.

    Returns:
        The closest ``mock_only`` marker, or ``None`` if the test has
        none.
    """
    return item.get_closest_marker(name=MOCK_ONLY_MARKER_NAME)


@beartype
def _marker_values(*, mark: pytest.Mark) -> tuple[UnverifiedReason, str]:
    """The reason and detail which a ``mock_only`` marker gives.

    Args:
        mark: The marker to read.

    Returns:
        The reason and the detail which the marker gives.

    Raises:
        TypeError: The marker does not give a valid reason and detail.
    """
    reason = mark.kwargs.get("reason")
    detail = mark.kwargs.get("detail")
    if not isinstance(reason, UnverifiedReason) or not isinstance(detail, str):
        message = (
            "A mock_only marker takes a reason from UnverifiedReason and a "
            f"detail string. Got reason={reason!r}, detail={detail!r}."
        )
        raise TypeError(message)
    return reason, detail


@beartype
def marker_reason(*, mark: pytest.Mark) -> UnverifiedReason:
    """The reason which a ``mock_only`` marker gives.

    Args:
        mark: The marker to read.

    Returns:
        The reason which the marker gives.
    """
    reason, _ = _marker_values(mark=mark)
    return reason


@beartype
def marker_detail(*, mark: pytest.Mark) -> str:
    """The detail which a ``mock_only`` marker gives.

    Args:
        mark: The marker to read.

    Returns:
        The detail which the marker gives.
    """
    _, detail = _marker_values(mark=mark)
    return detail


@beartype
def is_verified(*, items: list[pytest.Item], real_backend_id: str) -> bool:
    """Whether any of the items for one test is parametrized over real
    Vuforia.

    Args:
        items: The collected items for a single test function.
        real_backend_id: The parametrization ID which the real Vuforia
            backend is given.

    Returns:
        Whether the test runs against real Vuforia.
    """
    return any(
        real_backend_id in str.partition(item.nodeid, "[")[2] for item in items
    )


@beartype
def group_by_test(
    *,
    items: list[pytest.Item],
) -> dict[str, list[pytest.Item]]:
    """Group collected items by the test which they parametrize.

    Args:
        items: The collected items.

    Returns:
        The items for each test, keyed by the node ID of the test without
        its parametrization.
    """
    grouped: dict[str, list[pytest.Item]] = {}
    for item in items:
        grouped.setdefault(item.nodeid.split(sep="[")[0], []).append(item)
    return grouped


@beartype
def is_test_function(*, item: pytest.Item) -> bool:
    """Whether a collected item is a test function in this suite.

    Items collected from documentation by Sybil are not, and neither is
    anything else which is not a ``pytest`` function.

    Args:
        item: The collected item.

    Returns:
        Whether the item is a test function.
    """
    return isinstance(item, pytest.Function)
