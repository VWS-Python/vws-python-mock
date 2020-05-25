"""
Utilities for managing mock Vuforia databases.
"""

import uuid
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
