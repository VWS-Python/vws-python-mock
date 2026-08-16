"""A fake implementation of a Vuforia target manager."""

import threading
import time
from contextlib import AbstractContextManager
from typing import TYPE_CHECKING

from beartype import beartype

from mock_vws._services_validators.request_rate_validators import (
    RequestRateLimiter,
)
from mock_vws.database import CloudDatabase, VuMarkDatabase
from mock_vws.model_target import ModelTargetDataset, OAuth2ClientCredential
from mock_vws.reco_counts import RecoCountsReport

if TYPE_CHECKING:
    from mock_vws._database_matchers import AnyDatabase


@beartype
class TargetManager:
    """
    A target manager.

    See https://developer.vuforia.com/library/vuforia-engine/getting-started/engine-developer-portal/vuforia-target-manager/.
    """

    def __init__(self) -> None:
        """Create a target manager with no databases."""
        self._cloud_databases: set[CloudDatabase] = set()
        self._vumark_databases: set[VuMarkDatabase] = set()
        self._model_target_datasets: dict[str, ModelTargetDataset] = {}
        self._oauth2_client_credentials: dict[str, OAuth2ClientCredential] = {}
        self._reco_counts_reports: dict[str, RecoCountsReport] = {}
        self._lock = threading.RLock()
        self._request_rate_limiter = RequestRateLimiter(
            time_function=time.monotonic,
        )

    @property
    def lock(self) -> AbstractContextManager[bool]:
        """A re-entrant lock which guards this target manager's state.

        Every method of this class takes this lock.  Applications which are
        served on multiple threads, such as the Flask applications, must also
        take it around any other access to the databases in this target
        manager, including reading and writing the targets in a database, so
        that no request sees a database while another request is changing it.
        """
        return self._lock

    @property
    def request_rate_limiter(self) -> RequestRateLimiter:
        """The rate limiter for databases in this target manager."""
        return self._request_rate_limiter

    @property
    def cloud_databases(self) -> set[CloudDatabase]:
        """All cloud databases."""
        with self._lock:
            return set(self._cloud_databases)

    @property
    def vumark_databases(self) -> set[VuMarkDatabase]:
        """All VuMark databases."""
        with self._lock:
            return set(self._vumark_databases)

    @property
    def model_target_datasets(self) -> dict[str, ModelTargetDataset]:
        """All Model Target datasets, keyed by UUID."""
        with self._lock:
            return dict(self._model_target_datasets)

    @property
    def reco_counts_reports(self) -> dict[str, RecoCountsReport]:
        """All reco counts reports, keyed by report identifier."""
        with self._lock:
            return dict(self._reco_counts_reports)

    @property
    def oauth2_client_credentials(self) -> dict[str, OAuth2ClientCredential]:
        """All dynamically created OAuth2 client credentials."""
        return dict(self._oauth2_client_credentials)

    def add_oauth2_client_credential(
        self,
        credential: OAuth2ClientCredential,
    ) -> None:
        """Add an OAuth2 client credential."""
        self._oauth2_client_credentials[credential.client_id] = credential

    def remove_oauth2_client_credential(self, client_id: str) -> None:
        """Remove an OAuth2 client credential."""
        del self._oauth2_client_credentials[client_id]

    def add_reco_counts_report(
        self,
        reco_counts_report: RecoCountsReport,
    ) -> None:
        """Add a reco counts report."""
        with self._lock:
            self._reco_counts_reports[reco_counts_report.uuid_] = (
                reco_counts_report
            )

    def remove_cloud_database(self, cloud_database: CloudDatabase) -> None:
        """Remove a cloud database.

        Args:
            cloud_database: The cloud database to remove.

        Raises:
            KeyError: The cloud database is not in the target manager.
        """
        with self._lock:
            self._cloud_databases = {
                db for db in self._cloud_databases if db != cloud_database
            }
        self._request_rate_limiter.remove_database(database=cloud_database)

    def remove_vumark_database(self, vumark_database: VuMarkDatabase) -> None:
        """Remove a VuMark database.

        Args:
            vumark_database: The VuMark database to remove.
        """
        with self._lock:
            self._vumark_databases = {
                db for db in self._vumark_databases if db != vumark_database
            }

    def add_model_target_dataset(
        self,
        model_target_dataset: ModelTargetDataset,
    ) -> None:
        """Add a Model Target dataset."""
        with self._lock:
            self._model_target_datasets[model_target_dataset.uuid_] = (
                model_target_dataset
            )

    def remove_model_target_dataset(self, dataset_uuid: str) -> None:
        """Remove a Model Target dataset."""
        with self._lock:
            del self._model_target_datasets[dataset_uuid]

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
            'There is already a database with the {key_name} "{value}".'
        )
        with self._lock:
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
                        message = message_fmt.format(
                            key_name=key_name,
                            value=new,
                        )
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
                        message = message_fmt.format(
                            key_name=key_name,
                            value=new,
                        )
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
        with self._lock:
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
                        message = message_fmt.format(
                            key_name=key_name,
                            value=new,
                        )
                        raise ValueError(message)

            self._vumark_databases = {
                *self._vumark_databases,
                vumark_database,
            }
