"""Model Target dataset objects."""

import copy
import datetime
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Self, TypedDict
from zoneinfo import ZoneInfo

from beartype import beartype


class ModelTargetDatasetDict(TypedDict):
    """A dictionary type which represents a Model Target dataset."""

    request_body: dict[str, Any]
    dataset_type_name: str
    processing_time_seconds: float
    generation_failure_message: str | None
    generation_warning: dict[str, Any] | None
    uuid: str
    created_at: str


@beartype
class ModelTargetDatasetType(StrEnum):
    """The kind of Model Target dataset."""

    STANDARD = "standard"
    ADVANCED = "advanced"


@beartype
class ModelTargetRequest(StrEnum):
    """A Model Target dataset request phase."""

    CREATE = "create"
    STATUS = "status"
    DOWNLOAD = "download"
    DELETE = "delete"


@beartype
@dataclass(frozen=True, kw_only=True)
class ModelTargetFailureResponse:
    """A configured failure returned by Model Target dataset requests.

    OAuth2 token requests are always handled normally, so clients obtain a
    token before a configured dataset-request failure is returned.

    Args:
        status_code: The HTTP status code to return.
        headers: The HTTP response headers to return.
        body: The raw response body. String bodies are encoded as UTF-8 by
            the HTTP backend; byte bodies are returned unchanged.
        requests: The dataset request phases which return this response.
            By default, every dataset request phase returns it.
    """

    status_code: int
    headers: dict[str, str] = field(default_factory=dict[str, str])
    body: str | bytes = b""
    requests: frozenset[ModelTargetRequest] = field(
        default_factory=lambda: frozenset(ModelTargetRequest),
    )


@beartype
@dataclass(frozen=True, kw_only=True)
class OAuth2ClientCredential:
    """An OAuth2 client credential managed through the Vuforia Web API."""

    client_id: str
    client_secret: str
    scopes: tuple[str, ...]


@beartype
@dataclass(frozen=True, kw_only=True)
class ModelTargetGenerationFailure:
    """A configured Model Target dataset generation failure.

    Args:
        message: The failure message included in the dataset status response.
    """

    message: str = "Model Target dataset generation failed"


@beartype
@dataclass(frozen=True, kw_only=True)
class ModelTargetGenerationWarning:
    """A configured Model Target dataset generation warning.

    Args:
        message: The top-level warning message included in the dataset status
            response.
        details: The warning details included in the dataset status response.
    """

    message: str = "Warning after creating dataset"
    details: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {
                "code": "LOW_RECOGNITION_QUALITY",
                "message": (
                    "The processed model appears to have substandard "
                    "recognition quality."
                ),
            },
        ],
    )


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
        generation_failure: A failure to return when processing completes.
        generation_warning: A warning to return when processing completes.
    """

    request_body: dict[str, Any] = field(hash=False)
    dataset_type: ModelTargetDatasetType
    processing_time_seconds: float = field(hash=False)
    generation_failure: ModelTargetGenerationFailure | None = field(hash=False)
    generation_warning: ModelTargetGenerationWarning | None = field(hash=False)
    uuid_: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: datetime.datetime = field(default_factory=_now)

    @classmethod
    def from_dict(cls, dataset_dict: ModelTargetDatasetDict) -> Self:
        """Load a dataset from a dictionary."""
        generation_failure_message = dataset_dict["generation_failure_message"]
        if generation_failure_message is None:
            generation_failure = None
        else:
            generation_failure = ModelTargetGenerationFailure(
                message=generation_failure_message,
            )

        generation_warning_dict = dataset_dict["generation_warning"]
        if generation_warning_dict is None:
            generation_warning = None
        else:
            generation_warning = ModelTargetGenerationWarning(
                message=generation_warning_dict["message"],
                details=generation_warning_dict["details"],
            )

        dataset_type_name = dataset_dict["dataset_type_name"]
        return cls(
            request_body=dataset_dict["request_body"],
            dataset_type=ModelTargetDatasetType[dataset_type_name],
            processing_time_seconds=dataset_dict["processing_time_seconds"],
            generation_failure=generation_failure,
            generation_warning=generation_warning,
            uuid_=dataset_dict["uuid"],
            created_at=datetime.datetime.fromisoformat(
                dataset_dict["created_at"],
            ),
        )

    def to_dict(self) -> ModelTargetDatasetDict:
        """Dump a dataset to a dictionary which can be loaded as JSON."""
        generation_failure_message: str | None = None
        if self.generation_failure is not None:
            generation_failure_message = self.generation_failure.message

        generation_warning: dict[str, Any] | None = None
        if self.generation_warning is not None:
            generation_warning = {
                "message": self.generation_warning.message,
                "details": copy.deepcopy(x=self.generation_warning.details),
            }

        return {
            "request_body": copy.deepcopy(x=self.request_body),
            "dataset_type_name": self.dataset_type.name,
            "processing_time_seconds": self.processing_time_seconds,
            "generation_failure_message": generation_failure_message,
            "generation_warning": generation_warning,
            "uuid": self.uuid_,
            "created_at": self.created_at.isoformat(),
        }

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
        if self.generation_failure is not None:
            return "failed"
        return "done"

    def status_body(self) -> dict[str, Any]:
        """Return a status response body for this dataset."""
        status = self.status
        body: dict[str, Any] = {
            "status": status,
            "uuid": self.uuid_,
            "createdAt": _format_datetime(value=self.created_at),
        }
        if status == "processing":
            body["eta"] = _format_datetime(value=self.completed_at)
        else:
            body["completedAt"] = _format_datetime(value=self.completed_at)
        if status == "failed" and self.generation_failure is not None:
            body["error"] = {
                "code": "ERROR",
                "message": self.generation_failure.message,
            }
        if status == "done" and self.generation_warning is not None:
            body["warning"] = {
                "code": "WARNING",
                "message": self.generation_warning.message,
                "target": self.uuid_,
                "details": copy.deepcopy(x=self.generation_warning.details),
            }

        return body
