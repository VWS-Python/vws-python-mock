"""The database creation operation supplied by a mock backend."""

from typing import Protocol, runtime_checkable

from mock_vws.database import CloudDatabase


@runtime_checkable
class AddCloudDatabase(Protocol):
    """A backend operation which creates a cloud database."""

    def __call__(self, *, cloud_database: CloudDatabase) -> None:
        """Add the database to the running mock backend.

        Args:
            cloud_database: The database to add.
        """
        ...
