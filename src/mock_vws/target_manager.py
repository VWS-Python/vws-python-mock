"""A fake implementation of a Vuforia target manager."""

from beartype import beartype

from mock_vws.database import CloudDatabase, VuMarkDatabase

AnyDatabase = CloudDatabase | VuMarkDatabase


@beartype
class TargetManager:
    """
    A target manager.

    See https://developer.vuforia.com/target-manager.
    """

    def __init__(self) -> None:
        """Create a target manager with no databases."""
        self._cloud_databases: set[CloudDatabase] = set()
        self._vumark_databases: set[VuMarkDatabase] = set()

    @property
    def cloud_databases(self) -> set[CloudDatabase]:
        """All cloud databases."""
        return set(self._cloud_databases)

    @property
    def vumark_databases(self) -> set[VuMarkDatabase]:
        """All VuMark databases."""
        return set(self._vumark_databases)

    def remove_database(self, database: AnyDatabase) -> None:
        """Remove a database.

        Args:
            database: The database to remove.
        """
        if isinstance(database, CloudDatabase):
            self._cloud_databases = {
                db for db in self._cloud_databases if db != database
            }
        else:
            self._vumark_databases = {
                db for db in self._vumark_databases if db != database
            }

    def add_database(self, database: AnyDatabase) -> None:
        """Add a database.

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
        all_databases: list[AnyDatabase] = [
            *self._cloud_databases,
            *self._vumark_databases,
        ]
        for existing_db in all_databases:
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
                    existing_db.database_name,
                    database.database_name,
                    "name",
                ),
            ):
                if existing == new:
                    message = message_fmt.format(key_name=key_name, value=new)
                    raise ValueError(message)

        if isinstance(database, CloudDatabase):
            for existing_cloud_db in self._cloud_databases:
                for existing, new, key_name in (
                    (
                        existing_cloud_db.client_access_key,
                        database.client_access_key,
                        "client access key",
                    ),
                    (
                        existing_cloud_db.client_secret_key,
                        database.client_secret_key,
                        "client secret key",
                    ),
                ):
                    if existing == new:
                        message = message_fmt.format(
                            key_name=key_name, value=new
                        )
                        raise ValueError(message)
            self._cloud_databases = {*self._cloud_databases, database}
        else:
            self._vumark_databases = {*self._vumark_databases, database}
