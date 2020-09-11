"""
Utilities for managing mock Vuforia databases.
"""

import uuid
from dataclasses import dataclass, field
from typing import Set
from mock_vws._constants import ResultCodes, TargetStatuses

from .states import States
from .target import Target


def _random_hex() -> str:
    """
    Return a random hex value.
    """
    return uuid.uuid4().hex


@dataclass(eq=True, frozen=True)
class VuforiaDatabase:
    """
    A representation of a Vuforia target database.
    """

    # We hide a few things in the ``repr`` with ``repr=False`` so that they do
    # not show up in CI logs.
    database_name: str = field(default_factory=_random_hex, repr=False)
    server_access_key: str = field(default_factory=_random_hex, repr=False)
    server_secret_key: str = field(default_factory=_random_hex, repr=False)
    client_access_key: str = field(default_factory=_random_hex, repr=False)
    client_secret_key: str = field(default_factory=_random_hex, repr=False)
    targets: Set[Target] = field(default_factory=set, hash=False)
    state: States = States.WORKING

    @property
    def active_targets(self) -> Set[Target]:
        """
        """

        return set(
            [
                target
                for target in self.targets
                if target.status == TargetStatuses.SUCCESS.value
                and target.active_flag
                and not target.delete_date
            ],
        )

    @property
    def inactive_targets(self) -> Set[Target]:
        """
        """

        return set(
            [
                target
                for target in self.targets
                if target.status == TargetStatuses.SUCCESS.value
                and not target.active_flag
                and not target.delete_date
            ],
        )

    @property
    def failed_targets(self) -> Set[Target]:

        return set(
            [
                target
                for target in self.targets
                if target.status == TargetStatuses.FAILED.value
                and not target.delete_date
            ],
        )


    @property
    def processing_targets(self) -> Set[Target]:
        return set(
            [
                target
                for target in self.targets
                if target.status == TargetStatuses.PROCESSING.value
                and not target.delete_date
            ],
        )

