"""Model Target dataset objects."""

import datetime
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

from beartype import beartype


@beartype
class ModelTargetDatasetType(StrEnum):
    """The kind of Model Target dataset."""

    STANDARD = "standard"
    ADVANCED = "advanced"


@beartype
def _now() -> datetime.datetime:
    """Return the current time in UTC."""
    return datetime.datetime.now(tz=ZoneInfo(key="UTC"))


@beartype
def _format_datetime(value: datetime.datetime) -> str:
    """Format a timestamp like the Model Target Web API."""
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


@beartype
@dataclass(frozen=True, kw_only=True)
class ModelTargetDataset:
    """A Model Target dataset generation request.

    Args:
        request_body: The JSON request body used to start dataset creation.
        dataset_type: Whether this is a standard or advanced dataset.
        processing_time_seconds: The number of seconds before the generated
            dataset becomes available.
        uuid_: The dataset UUID.
        created_at: When the dataset creation was requested.
    """

    request_body: dict[str, Any] = field(hash=False)
    dataset_type: ModelTargetDatasetType
    processing_time_seconds: float = field(hash=False)
    uuid_: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: datetime.datetime = field(default_factory=_now)

    @property
    def completed_at(self) -> datetime.datetime:
        """When the dataset completes processing."""
        return self.created_at + datetime.timedelta(
            seconds=self.processing_time_seconds,
        )

    @property
    def status(self) -> str:
        """The current dataset generation status."""
        if _now() < self.completed_at:
            return "processing"
        return "done"

    def status_body(self) -> dict[str, Any]:
        """Return a status response body for this dataset."""
        body: dict[str, Any] = {
            "status": self.status,
            "uuid": self.uuid_,
            "createdAt": _format_datetime(value=self.created_at),
        }
        if self.status == "processing":
            body["eta"] = _format_datetime(value=self.completed_at)
        else:
            body["completedAt"] = _format_datetime(value=self.completed_at)

        return body
