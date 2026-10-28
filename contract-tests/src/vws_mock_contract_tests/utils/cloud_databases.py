"""The database creation operation supplied by a mock backend."""

from typing import Protocol, runtime_checkable

from vws_mock_contract_tests.fixtures.credentials import (
    NamedCloudDatabaseCredentials,
)


@runtime_checkable
class CreateCloudDatabase(Protocol):
    """A backend operation which creates a cloud database."""

    def __call__(self) -> NamedCloudDatabaseCredentials:
        """Create a database and return its name and credentials.

        Returns:
            The name and credentials of the new database.
        """
        ...
