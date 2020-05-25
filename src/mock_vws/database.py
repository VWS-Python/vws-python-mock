"""
Utilities for managing mock Vuforia databases.
"""

import uuid
from typing import Dict, List, Optional, Set, Union
from dataclasses import dataclass, field
from typing import Set

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
    Credentials for VWS APIs.
    """

    database_name: str = field(default_factory=_random_hex)
    server_access_key: str = field(default_factory=_random_hex)
    server_secret_key: str = field(default_factory=_random_hex)
    client_access_key: str = field(default_factory=_random_hex)
    client_secret_key: str = field(default_factory=_random_hex)
    targets: Set[Target] = field(default_factory=set, hash=False)
    state: States = States.WORKING

    # TODO use built in dataclass to dict feature?
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
