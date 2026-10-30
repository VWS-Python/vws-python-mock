"""Behavior declared by an adapter for the shared API tests."""

from dataclasses import dataclass

from beartype import beartype


@beartype
@dataclass(frozen=True, kw_only=True)
class BackendCapabilities:
    """The behavior and checks supported by the running service.

    ``fast_oversized_content_length_response`` enables requests whose
    declared body length exceeds their actual length. Services which wait
    too long for the missing bytes cannot run that check.
    """

    fast_oversized_content_length_response: bool
