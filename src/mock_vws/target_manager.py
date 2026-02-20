"""A fake implementation of a Vuforia target manager."""

from typing import TYPE_CHECKING

from beartype import beartype

from mock_vws.database import CloudDatabase

if TYPE_CHECKING:
    from collections.abc import Iterable


@beartype
class TargetManager:
    """
    A target manager.

    See https://developer.vuforia.com/target-manager.
    """

    def __init__(self) -> None:
        """Create a target manager with no databases."""
        self._databases: Iterable[CloudDatabase] = set()

    def remove_database(self, database: CloudDatabase) -> None:
        """Remove a cloud database.

        Args:
            database: The database to add.

        Raises:
            KeyError: The database is not in the target manager.
        """
        self._databases = {db for db in self._databases if db != database}

    def add_database(self, database: CloudDatabase) -> None:
        """Add a cloud database.

        Args:
            database: The database to add.

        Raises:
            ValueError: One of the given database keys matches a key for an
                existing database.
        """
        message_fmt = (
            "All {key_name}s must be unique. "
            'There is already a database with the {key_name} "{value}".'
        )
        for existing_db in self.databases:
            for existing, new, key_name in (
                (
                    existing_db.server_access_key,
                    database.server_access_key,
                    "server access key",
                ),
                (
                    existing_db.server_secret_key,
                    database.server_secret_key,
                    "server secret key",
                ),
                (
                    existing_db.client_access_key,
                    database.client_access_key,
                    "client access key",
                ),
                (
                    existing_db.client_secret_key,
                    database.client_secret_key,
                    "client secret key",
                ),
                (
                    existing_db.database_name,
                    database.database_name,
                    "name",
                ),
            ):
                if existing == new:
                    message = message_fmt.format(key_name=key_name, value=new)
                    raise ValueError(message)

        self._databases = {*self._databases, database}

    @property
    def databases(self) -> set[CloudDatabase]:
        """All cloud databases."""
        return set(self._databases)
