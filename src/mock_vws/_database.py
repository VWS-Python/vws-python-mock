"""
Utilities for managing mock Vuforia databases.
"""

import uuid
from typing import List, Optional

from ._target import Target
from .states import States


class VuforiaDatabase:
    """
    Credentials for VWS APIs.
    """

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
            targets: The ``Target``\s in the database.
            state: The state of the database.
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

        self.server_access_key: bytes = bytes(
            server_access_key,
            encoding='utf-8',
        )
        self.server_secret_key: bytes = bytes(
            server_secret_key,
            encoding='utf-8',
        )
        self.client_access_key: bytes = bytes(
            client_access_key,
            encoding='utf-8',
        )
        self.client_secret_key: bytes = bytes(
            client_secret_key,
            encoding='utf-8',
        )
        self.database_name = database_name
        self.targets: List[Target] = []
        self.state = state
