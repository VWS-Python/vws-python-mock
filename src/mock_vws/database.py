"""
Utilities for managing mock Vuforia databases.
"""

from __future__ import annotations

import base64
import datetime
import io
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Union

from backports.zoneinfo import ZoneInfo

from mock_vws._constants import TargetStatuses
from mock_vws.states import States
from mock_vws.target import Target


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
    ) -> Dict[
        str,
        Union[
            str,
            List[Dict[str, Optional[Union[str, int, bool, float]]]],
        ],
    ]:
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
    def from_dict(cls, database_dict) -> VuforiaDatabase:
        database_name = database_dict['database_name']
        server_access_key = database_dict['server_access_key']
        server_secret_key = database_dict['server_secret_key']
        client_access_key = database_dict['client_access_key']
        client_secret_key = database_dict['client_secret_key']
        state = States(database_dict['state_value'])

        new_database = cls(
            database_name=database_name,
            server_access_key=server_access_key,
            server_secret_key=server_secret_key,
            client_access_key=client_access_key,
            client_secret_key=client_secret_key,
            state=state,
        )
        for target_dict in database_dict['targets']:
            # TODO target.from_dict()
            name = target_dict['name']
            active_flag = target_dict['active_flag']
            width = target_dict['width']
            image_base64 = target_dict['image_base64']
            image_bytes = base64.b64decode(image_base64)
            image = io.BytesIO(image_bytes)
            processing_time_seconds = target_dict['processing_time_seconds']
            application_metadata = target_dict['application_metadata']

            target = Target(
                name=name,
                active_flag=active_flag,
                width=width,
                image=image,
                processing_time_seconds=processing_time_seconds,
                application_metadata=application_metadata,
            )
            target.target_id = target_dict['target_id']
            gmt = ZoneInfo('GMT')
            target.last_modified_date = datetime.datetime.fromisoformat(
                target_dict['last_modified_date'],
            )
            target.last_modified_date = target.last_modified_date.replace(
                tzinfo=gmt,
            )
            target.upload_date = datetime.datetime.fromisoformat(
                target_dict['upload_date'],
            )
            target.processed_tracking_rating = target_dict[
                'processed_tracking_rating'
            ]
            target.upload_date = target.upload_date.replace(tzinfo=gmt)
            delete_date_optional = target_dict['delete_date_optional']
            if delete_date_optional:
                target.delete_date = datetime.datetime.fromisoformat(
                    delete_date_optional,
                )
                target.delete_date = target.delete_date.replace(tzinfo=gmt)
            new_database.targets.add(target)

        return new_database

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
