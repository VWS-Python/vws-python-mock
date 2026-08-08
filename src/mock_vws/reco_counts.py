"""Reco counts report objects."""

import datetime
import uuid
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from beartype import beartype

# The mock does not count recognitions, so a generated report never has any
# rows for targets.
# Real Vuforia ends the header row with a carriage return and a line feed.
_CSV_CONTENT = "target_id,reco_count\r\n"


@beartype
def _now() -> datetime.datetime:
    """Return the current time in UTC."""
    return datetime.datetime.now(tz=ZoneInfo(key="UTC"))


@beartype
@dataclass(frozen=True, kw_only=True)
class RecoCountsReport:
    """A requested reco counts report.

    Args:
        generation_time_seconds: The number of seconds before the report is
            available to download.
        uuid_: The report identifier, used in the report's download URL.
        created_at: When the report was requested.
    """

    generation_time_seconds: float = field(hash=False)
    uuid_: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: datetime.datetime = field(default_factory=_now)

    @property
    def available_at(self) -> datetime.datetime:
        """When the report becomes available to download."""
        return self.created_at + datetime.timedelta(
            seconds=self.generation_time_seconds,
        )

    @property
    def is_available(self) -> bool:
        """Whether the report is available to download."""
        return _now() >= self.available_at

    @property
    def csv_content(self) -> str:
        """The content of the generated CSV report."""
        return _CSV_CONTENT
