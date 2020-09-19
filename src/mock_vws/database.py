"""
Utilities for managing mock Vuforia databases.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Set, TypedDict, Union

from mock_vws._constants import TargetStatuses
from mock_vws.states import States
from mock_vws.target import Target, TargetDict


class DatabaseDict(TypedDict):
    database_name: str
    server_access_key: str
    server_secret_key: str
    client_access_key: str
    client_secret_key: str
    state_value: str
    targets: List[TargetDict]


def _random_hex() -> str:
    """
    Return a random hex value.
    """
    return uuid.uuid4().hex


@dataclass(eq=True, frozen=True)
class VuforiaDatabase:
    """
    Credentials for VWS APIs.
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

    request_quota = 100000
    reco_threshold = 1000
    current_month_recos = 0
    previous_month_recos = 0
    total_recos = 0
    target_quota = 1000

    def to_dict(
        self,
    ) -> Dict[str, Union[str, List[TargetDict]]]:
        targets = [target.to_dict() for target in self.targets]
        return {
            'database_name': self.database_name,
            'server_access_key': self.server_access_key,
            'server_secret_key': self.server_secret_key,
            'client_access_key': self.client_access_key,
            'client_secret_key': self.client_secret_key,
            'state_value': self.state.value,
            'targets': targets,
        }

    @classmethod
    def from_dict(cls, database_dict: DatabaseDict) -> VuforiaDatabase:
        database = cls(
            database_name=database_dict['database_name'],
            server_access_key=database_dict['server_access_key'],
            server_secret_key=database_dict['server_secret_key'],
            client_access_key=database_dict['client_access_key'],
            client_secret_key=database_dict['client_secret_key'],
            state=States(database_dict['state_value']),
        )

        for target_dict in database_dict['targets']:
            target = Target.from_dict(target_dict=target_dict)
            database.targets.add(target)

        return database

    @property
    def not_deleted_targets(self) -> Set[Target]:
        """
        All targets which have not been deleted.
        """
        return set(target for target in self.targets if not target.delete_date)

    @property
    def active_targets(self) -> Set[Target]:
        """
        All active targets.
        """
        return set(
            target
            for target in self.not_deleted_targets
            if target.status == TargetStatuses.SUCCESS.value
            and target.active_flag
        )

    @property
    def inactive_targets(self) -> Set[Target]:
        """
        All inactive targets.
        """
        return set(
            target
            for target in self.not_deleted_targets
            if target.status == TargetStatuses.SUCCESS.value
            and not target.active_flag
        )

    @property
    def failed_targets(self) -> Set[Target]:
        """
        All failed targets.
        """
        return set(
            target
            for target in self.not_deleted_targets
            if target.status == TargetStatuses.FAILED.value
        )

    @property
    def processing_targets(self) -> Set[Target]:
        """
        All processing targets.
        """
        return set(
            target
            for target in self.not_deleted_targets
            if target.status == TargetStatuses.PROCESSING.value
        )
