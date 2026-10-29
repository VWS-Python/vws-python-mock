"""Utilities for managing mock Vuforia databases."""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Self, TypedDict

from beartype import beartype

from mock_vws.states import States
from mock_vws.target import (
    VuMarkTarget,
    VuMarkTargetDict,
)


@beartype
class VuMarkDatabaseDict(TypedDict):
    """A dictionary type which represents a VuMark database."""

    database_name: str
    server_access_key: str
    server_secret_key: str
    vumark_targets: Iterable[VuMarkTargetDict]
    state_name: str


@beartype
def _random_hex() -> str:
    """Return a random hex value."""
    return uuid.uuid4().hex


@beartype
@dataclass(eq=True, frozen=True, kw_only=True)
class VuMarkDatabase:
    """Credentials for the VuMark generation API.

    Args:
        database_name: The name of a VWS target manager database name. Defaults
            to a random string.
        server_access_key: A VWS server access key. Defaults to a random
            string.
        server_secret_key: A VWS server secret key. Defaults to a random
            string.
    """

    database_name: str = field(default_factory=_random_hex, repr=False)
    server_access_key: str = field(default_factory=_random_hex, repr=False)
    server_secret_key: str = field(default_factory=_random_hex, repr=False)
    # We have ``vumark_targets`` as ``hash=False`` so that we can have the
    # class as ``frozen=True`` while still being able to keep the interface
    # we want.
    vumark_targets: set[VuMarkTarget] = field(
        default_factory=set[VuMarkTarget],
        hash=False,
    )
    state: States = States.WORKING

    def get_vumark_target(self, target_id: str) -> VuMarkTarget:
        """Return a VuMark target from the database with the given ID."""
        (target,) = (
            target
            for target in self.vumark_targets
            if target.target_id == target_id
        )
        return target

    def to_dict(self) -> VuMarkDatabaseDict:
        """Dump a VuMark database to a dictionary which can be loaded as
        JSON.
        """
        vumark_targets = [target.to_dict() for target in self.vumark_targets]
        return {
            "database_name": self.database_name,
            "server_access_key": self.server_access_key,
            "server_secret_key": self.server_secret_key,
            "vumark_targets": vumark_targets,
            "state_name": self.state.name,
        }

    @classmethod
    def from_dict(cls, database_dict: VuMarkDatabaseDict) -> Self:
        """Load a VuMark database from a dictionary."""
        return cls(
            database_name=database_dict["database_name"],
            server_access_key=database_dict["server_access_key"],
            server_secret_key=database_dict["server_secret_key"],
            vumark_targets={
                VuMarkTarget.from_dict(target_dict=target_dict)
                for target_dict in database_dict["vumark_targets"]
            },
            state=States[database_dict["state_name"]],
        )

    @property
    def not_deleted_targets(self) -> set[VuMarkTarget]:
        """All VuMark targets."""
        return set(self.vumark_targets)
