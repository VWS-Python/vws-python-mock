"""Utilities for managing mock Vuforia databases."""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Self, TypedDict, cast

from beartype import beartype

from mock_vws._constants import TargetStatuses
from mock_vws.database_type import DatabaseType
from mock_vws.states import States
from mock_vws.target import (
    ImageTarget,
    ImageTargetDict,
    VuMarkTarget,
    VuMarkTargetDict,
)


@beartype
class CloudDatabaseDict(TypedDict):
    """A dictionary type which represents a cloud database."""

    database_name: str
    server_access_key: str
    server_secret_key: str
    client_access_key: str
    client_secret_key: str
    state_name: str
    database_type_name: str
    targets: Iterable[ImageTargetDict | VuMarkTargetDict]


@beartype
def _random_hex() -> str:
    """Return a random hex value."""
    return uuid.uuid4().hex


@beartype
@dataclass(eq=True, frozen=True)
class CloudDatabase:
    """Credentials for VWS APIs.

    Args:
        database_name: The name of a VWS target manager database name. Defaults
            to a random string.
        server_access_key: A VWS server access key. Defaults to a random
            string.
        server_secret_key: A VWS server secret key. Defaults to a random
            string.
        client_access_key: A VWS client access key. Defaults to a random
            string.
        client_secret_key: A VWS client secret key. Defaults to a random
            string.
        state: The state of the database.
    """

    # We hide a few things in the ``repr`` with ``repr=False`` so that they do
    # not show up in CI logs.
    database_name: str = field(default_factory=_random_hex, repr=False)
    server_access_key: str = field(default_factory=_random_hex, repr=False)
    server_secret_key: str = field(default_factory=_random_hex, repr=False)
    client_access_key: str = field(default_factory=_random_hex, repr=False)
    client_secret_key: str = field(default_factory=_random_hex, repr=False)
    # We have ``targets`` as ``hash=False`` so that we can have the class as
    # ``frozen=True`` while still being able to keep the interface we want.
    # In particular, we might want to inspect the ``database`` object's targets
    # as they change via API requests.
    targets: set[ImageTarget | VuMarkTarget] = field(
        default_factory=set[ImageTarget | VuMarkTarget],
        hash=False,
    )
    state: States = States.WORKING
    database_type: DatabaseType = DatabaseType.CLOUD_RECO

    request_quota: int = 100000
    reco_threshold: int = 1000
    current_month_recos: int = 0
    previous_month_recos: int = 0
    total_recos: int = 0
    target_quota: int = 1000

    def to_dict(self) -> CloudDatabaseDict:
        """Dump a target to a dictionary which can be loaded as JSON."""
        targets: list[ImageTargetDict | VuMarkTargetDict] = [
            target.to_dict() for target in self.targets
        ]
        return {
            "database_name": self.database_name,
            "server_access_key": self.server_access_key,
            "server_secret_key": self.server_secret_key,
            "client_access_key": self.client_access_key,
            "client_secret_key": self.client_secret_key,
            "state_name": self.state.name,
            "database_type_name": self.database_type.name,
            "targets": targets,
        }

    def get_target(self, target_id: str) -> ImageTarget | VuMarkTarget:
        """Return a target from the database with the given ID."""
        (target,) = (
            target for target in self.targets if target.target_id == target_id
        )
        return target

    @classmethod
    def from_dict(cls, database_dict: CloudDatabaseDict) -> Self:
        """Load a database from a dictionary."""
        targets: set[ImageTarget | VuMarkTarget] = set()
        for target_dict in database_dict["targets"]:
            if target_dict["target_type_name"] == "VUMARK_TEMPLATE":
                targets.add(
                    VuMarkTarget.from_dict(
                        target_dict=target_dict,
                    )
                )
            else:
                targets.add(
                    ImageTarget.from_dict(
                        target_dict=cast("ImageTargetDict", target_dict),
                    )
                )

        return cls(
            database_name=database_dict["database_name"],
            server_access_key=database_dict["server_access_key"],
            server_secret_key=database_dict["server_secret_key"],
            client_access_key=database_dict["client_access_key"],
            client_secret_key=database_dict["client_secret_key"],
            state=States[database_dict["state_name"]],
            database_type=DatabaseType[database_dict["database_type_name"]],
            targets=targets,
        )

    @property
    def not_deleted_targets(self) -> set[ImageTarget | VuMarkTarget]:
        """All targets which have not been deleted."""
        return {target for target in self.targets if not target.delete_date}

    @property
    def active_targets(self) -> set[ImageTarget | VuMarkTarget]:
        """All active targets."""
        return {
            target
            for target in self.not_deleted_targets
            if target.status == TargetStatuses.SUCCESS.value
            and target.active_flag
        }

    @property
    def inactive_targets(self) -> set[ImageTarget | VuMarkTarget]:
        """All inactive targets."""
        return {
            target
            for target in self.not_deleted_targets
            if target.status == TargetStatuses.SUCCESS.value
            and not target.active_flag
        }

    @property
    def failed_targets(self) -> set[ImageTarget | VuMarkTarget]:
        """All failed targets."""
        return {
            target
            for target in self.not_deleted_targets
            if target.status == TargetStatuses.FAILED.value
        }

    @property
    def processing_targets(self) -> set[ImageTarget | VuMarkTarget]:
        """All processing targets."""
        return {
            target
            for target in self.not_deleted_targets
            if target.status == TargetStatuses.PROCESSING.value
        }
