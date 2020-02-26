"""
Utilities for managing mock Vuforia databases.
"""

import uuid
from typing import Dict, List, Optional, Union

from .states import States
from .target import Target


# This would be simpler as a dataclass, but
# https://github.com/agronholm/sphinx-autodoc-typehints/issues/123 blocks us
# doing that.
class VuforiaDatabase:
    """
    Credentials for VWS APIs.
    """

    database_name: str
    server_access_key: str
    server_secret_key: str
    client_access_key: str
    client_secret_key: str
    targets: List[Target]
    state: States

    def __init__(
        self,
        server_access_key: Optional[str] = None,
        server_secret_key: Optional[str] = None,
        client_access_key: Optional[str] = None,
        client_secret_key: Optional[str] = None,
        database_name: Optional[str] = None,
        state: States = States.WORKING,
    ) -> None:
        """
        Args:
            database_name: The name of a VWS target manager database name.
            server_access_key: A VWS server access key.
            server_secret_key: A VWS server secret key.
            client_access_key: A VWS client access key.
            client_secret_key: A VWS client secret key.
            state: The state of the database.

        Attributes:
            database_name (str): The name of a VWS target manager database.
            server_access_key (bytes): A VWS server access key.
            server_secret_key (bytes): A VWS server secret key.
            client_access_key (bytes): A VWS client access key.
            client_secret_key (bytes): A VWS client secret key.
            targets (typing.List[Target]): The
                :class:`~mock_vws.target.Target` s in the database.
            state (States): The state of the database.
        """

        if database_name is None:
            database_name = uuid.uuid4().hex

        if server_access_key is None:
            server_access_key = uuid.uuid4().hex

        if server_secret_key is None:
            server_secret_key = uuid.uuid4().hex

        if client_access_key is None:
            client_access_key = uuid.uuid4().hex

        if client_secret_key is None:
            client_secret_key = uuid.uuid4().hex

        self.server_access_key = server_access_key
        self.server_secret_key = server_secret_key
        self.client_access_key = client_access_key
        self.client_secret_key = client_secret_key
        self.database_name = database_name
        self.targets: List[Target] = []
        self.state = state

    def to_dict(self) -> Dict[str, Union[str, List[Dict[str, Optional[Union[str, int, bool, float]]]]]]:
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
