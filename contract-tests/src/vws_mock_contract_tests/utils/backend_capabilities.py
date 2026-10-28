"""Behavior declared by an adapter for the shared API tests."""

from dataclasses import dataclass

from beartype import beartype


@beartype
@dataclass(frozen=True, kw_only=True)
class BackendCapabilities:
    """The behavior and checks supported by the running service.

    ``deterministic_target_order`` covers upload-date ordering for target
    lists and duplicate lists. ``deterministic_query_order`` covers that
    ordering for matches to identical images.

    ``fast_oversized_content_length_response`` enables requests whose
    declared body length exceeds their actual length. Services which wait
    too long for the missing bytes cannot run that check.

    ``rolling_rate_limit_window`` enables the exact request-sequence
    assertion for a fresh database. Services with a fixed clock window
    still run the common rate-limit assertions.
    """

    deterministic_target_order: bool
    deterministic_query_order: bool
    fast_oversized_content_length_response: bool
    rolling_rate_limit_window: bool
