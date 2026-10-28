"""Credential data shared by API tests and backend adapters."""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@runtime_checkable
class CloudDatabaseCredentials(Protocol):
    """Read-only cloud database access supplied by a backend adapter.

    Shared HTTP helpers need credentials and the database ID, without
    depending on the mock's database state or storage implementation.
    """

    @property
    def database_id(self) -> str:
        """The identifier used in recognition-report URLs."""
        ...

    @property
    def server_access_key(self) -> str:
        """The access key used to sign VWS requests."""
        ...

    @property
    def server_secret_key(self) -> str:
        """The secret key used to sign VWS requests."""
        ...

    @property
    def client_access_key(self) -> str:
        """The access key used to sign VWQ requests."""
        ...

    @property
    def client_secret_key(self) -> str:
        """The secret key used to sign VWQ requests."""
        ...


@dataclass(frozen=True, kw_only=True)
class InactiveVuMarkCloudDatabase:
    """Credentials for an inactive VuMark database."""

    target_manager_database_name: str = field(repr=False)
    server_access_key: str = field(repr=False)
    server_secret_key: str = field(repr=False)


@dataclass(frozen=True, kw_only=True)
class VuMarkCloudDatabase:
    """Credentials for the VuMark generation API."""

    target_manager_database_name: str = field(repr=False)
    server_access_key: str = field(repr=False)
    server_secret_key: str = field(repr=False)
    target_id: str = field(repr=False)
    processing_target_id: str = field(repr=False)


@dataclass(frozen=True, kw_only=True)
class ModelTargetCredentials:
    """Credentials and input data for the Model Target Web API."""

    client_id: str = field(repr=False)
    client_secret: str = field(repr=False)
    cad_data_url: str = field(repr=False)
    username: str = field(repr=False)
    password: str = field(repr=False)
