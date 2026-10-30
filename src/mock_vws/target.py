"""A fake implementation of a target for the Vuforia Web Services API."""

import datetime as dt
import uuid
from dataclasses import dataclass, field
from typing import Self, TypedDict
from zoneinfo import ZoneInfo

from beartype import BeartypeConf, beartype

from mock_vws._constants import TargetStatuses


class VuMarkTargetDict(TypedDict):
    """A dictionary type which represents a VuMark target."""

    target_id: str
    name: str
    processing_time_seconds: int | float
    last_modified_date: str
    upload_date: str


@beartype
def _random_hex() -> str:
    """Return a random hex value."""
    return uuid.uuid4().hex


@beartype
def _time_now() -> dt.datetime:
    """Return the current time in the GMT time zone."""
    gmt = ZoneInfo(key="GMT")
    return dt.datetime.now(tz=gmt)


@beartype(conf=BeartypeConf(is_pep484_tower=True))
@dataclass(frozen=True, eq=True, kw_only=True)
class VuMarkTarget:
    """
    A VuMark target as managed in the Vuforia Target Manager.

    VuMark targets use a VuMark template.
    """

    name: str
    processing_time_seconds: int | float = 0.0
    target_id: str = field(default_factory=_random_hex)
    last_modified_date: dt.datetime = field(default_factory=_time_now)
    upload_date: dt.datetime = field(default_factory=_time_now)

    @property
    def status(self) -> str:
        """Return the status of the target.

        VuMark targets always succeed after processing.
        Zero processing time means immediate success, even when the last
        modified date is ahead of the server clock. A positive duration keeps
        the target processing until the exact completion timestamp.
        """
        processing_time = dt.timedelta(
            seconds=float(self.processing_time_seconds),
        )

        timezone = self.upload_date.tzinfo
        now = dt.datetime.now(tz=timezone)
        time_since_change = max(dt.timedelta(), now - self.last_modified_date)

        if time_since_change < processing_time:
            return TargetStatuses.PROCESSING.value

        return TargetStatuses.SUCCESS.value

    @classmethod
    def from_dict(cls, target_dict: VuMarkTargetDict) -> Self:
        """Load a VuMark target from a dictionary."""
        timezone = ZoneInfo(key="GMT")
        last_modified_date = dt.datetime.fromisoformat(
            target_dict["last_modified_date"],
        ).replace(tzinfo=timezone)
        upload_date = dt.datetime.fromisoformat(
            target_dict["upload_date"],
        ).replace(tzinfo=timezone)
        return cls(
            target_id=target_dict["target_id"],
            name=target_dict["name"],
            processing_time_seconds=target_dict["processing_time_seconds"],
            last_modified_date=last_modified_date,
            upload_date=upload_date,
        )

    def to_dict(self) -> VuMarkTargetDict:
        """Dump a VuMark target to a dictionary which can be loaded as
        JSON.
        """
        return {
            "target_id": self.target_id,
            "name": self.name,
            "processing_time_seconds": float(self.processing_time_seconds),
            "last_modified_date": self.last_modified_date.isoformat(),
            "upload_date": self.upload_date.isoformat(),
        }
