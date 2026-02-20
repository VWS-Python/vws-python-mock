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

    def remove_cloud_database(self, cloud_database: CloudDatabase) -> None:
        """Remove a cloud database.

        Args:
            cloud_database: The cloud database to remove.

        Raises:
            KeyError: The cloud database is not in the target manager.
        """
        self._cloud_databases = {
            db for db in self._cloud_databases if db != cloud_database
        }

    def remove_vumark_database(self, vumark_database: VuMarkDatabase) -> None:
        """Remove a VuMark database.

        Args:
            vumark_database: The VuMark database to remove.
        """
        self._vumark_databases = {
            db for db in self._vumark_databases if db != vumark_database
        }

    def add_cloud_database(self, cloud_database: CloudDatabase) -> None:
        """Add a cloud database.

        Args:
            cloud_database: The cloud database to add.

        Raises:
            ValueError: One of the given cloud database keys matches a key for
                an existing cloud database.
        """
        message_fmt = (
            "All {key_name}s must be unique. "
            'There is already a cloud database with the {key_name} "{value}".'
        )
        all_databases: list[AnyDatabase] = [
            *self._cloud_databases,
            *self._vumark_databases,
        ]
        for existing_db in all_databases:
            for existing, new, key_name in (
                (
                    existing_db.server_access_key,
                    cloud_database.server_access_key,
                    "server access key",
                ),
                (
                    existing_db.server_secret_key,
                    cloud_database.server_secret_key,
                    "server secret key",
                ),
                (
                    existing_db.database_name,
                    cloud_database.database_name,
                    "name",
                ),
            ):
                if existing == new:
                    message = message_fmt.format(key_name=key_name, value=new)
                    raise ValueError(message)

        for existing_cloud_db in self._cloud_databases:
            for existing, new, key_name in (
                (
                    existing_cloud_db.client_access_key,
                    cloud_database.client_access_key,
                    "client access key",
                ),
                (
                    existing_cloud_db.client_secret_key,
                    cloud_database.client_secret_key,
                    "client secret key",
                ),
            ):
                if existing == new:
                    message = message_fmt.format(key_name=key_name, value=new)
                    raise ValueError(message)

        self._cloud_databases = {*self._cloud_databases, cloud_database}

    def add_vumark_database(self, vumark_database: VuMarkDatabase) -> None:
        """Add a VuMark database.

        Args:
            vumark_database: The VuMark database to add.

        Raises:
            ValueError: One of the given database keys matches a key for
                an existing database.
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
                    vumark_database.server_access_key,
                    "server access key",
                ),
                (
                    existing_db.server_secret_key,
                    vumark_database.server_secret_key,
                    "server secret key",
                ),
                (
                    existing_db.database_name,
                    vumark_database.database_name,
                    "name",
                ),
            ):
                if existing == new:
                    message = message_fmt.format(key_name=key_name, value=new)
                    raise ValueError(message)

        self._vumark_databases = {*self._vumark_databases, vumark_database}
