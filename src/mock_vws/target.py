"""
A fake implementation of a target for the Vuforia Web Services API.
"""
from __future__ import annotations

import base64
import datetime
import io
import statistics
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypedDict
from zoneinfo import ZoneInfo

from PIL import Image, ImageStat

from mock_vws._constants import TargetStatuses
from mock_vws.target_raters import HardcodedTargetTrackingRater

if TYPE_CHECKING:
    from mock_vws.target_raters import TargetTrackingRater


class TargetDict(TypedDict):
    """
    A dictionary type which represents a target.
    """

    name: str
    width: float
    image_base64: str
    active_flag: bool
    processing_time_seconds: int | float
    application_metadata: str | None
    target_id: str
    last_modified_date: str
    delete_date_optional: str | None
    upload_date: str
    tracking_rating: int


def _random_hex() -> str:
    """
    Return a random hex value.
    """
    return uuid.uuid4().hex


def _time_now() -> datetime.datetime:
    """
    Return the current time in the GMT time zone.
    """
    gmt = ZoneInfo("GMT")
    return datetime.datetime.now(tz=gmt)


@dataclass(frozen=True, eq=True)
class Target:
    """
    A Vuforia Target as managed in
    https://developer.vuforia.com/target-manager.
    """

    active_flag: bool
    application_metadata: str | None
    image_value: bytes
    name: str
    processing_time_seconds: float
    width: float
    target_tracking_rater: TargetTrackingRater = field(compare=False)
    current_month_recos: int = 0
    delete_date: datetime.datetime | None = None
    last_modified_date: datetime.datetime = field(default_factory=_time_now)
    previous_month_recos: int = 0
    reco_rating: str = ""
    target_id: str = field(default_factory=_random_hex)
    total_recos: int = 0
    upload_date: datetime.datetime = field(default_factory=_time_now)

    @property
    def _post_processing_status(self) -> TargetStatuses:
        """
        Return the status of the target, or what it will be when processing is
        finished.

        The status depends on the standard deviation of the color bands.
        How VWS determines this is unknown, but it relates to how suitable the
        target is for detection.
        """
        image_file = io.BytesIO(self.image_value)
        image = Image.open(image_file)
        image_stat = ImageStat.Stat(image)

        average_std_dev = statistics.mean(image_stat.stddev)

        success_threshold = 5

        if average_std_dev > success_threshold:
            return TargetStatuses.SUCCESS

        return TargetStatuses.FAILED

    @property
    def status(self) -> str:
        """
        Return the status of the target.

        For now this waits half a second (arbitrary) before changing the
        status from 'processing' to 'failed' or 'success'.

        The status depends on the standard deviation of the color bands.
        How VWS determines this is unknown, but it relates to how suitable the
        target is for detection.
        """
        processing_time = datetime.timedelta(
            seconds=self.processing_time_seconds,
        )

        timezone = self.upload_date.tzinfo
        now = datetime.datetime.now(tz=timezone)
        time_since_change = now - self.last_modified_date

        if time_since_change <= processing_time:
            return str(TargetStatuses.PROCESSING.value)

        return str(self._post_processing_status.value)

    @property
    def _post_processing_target_rating(self) -> int:
        return self.target_tracking_rater(image_content=self.image_value)

    @property
    def tracking_rating(self) -> int:
        """
        Return the tracking rating of the target recognition image.
        """
        pre_rating_time = datetime.timedelta(
            # That this is half of the total processing time is unrealistic.
            # In VWS it is not a constant percentage.
            seconds=self.processing_time_seconds / 2,
        )

        timezone = self.upload_date.tzinfo
        now = datetime.datetime.now(tz=timezone)
        time_since_upload = now - self.upload_date

        # The real VWS seems to give -1 for a short time while processing, then
        # the real rating, even while it is still processing.
        if time_since_upload <= pre_rating_time:
            return -1

        return self._post_processing_target_rating

    @classmethod
    def from_dict(cls, target_dict: TargetDict) -> Target:
        """
        Load a target from a dictionary.
        """
        timezone = ZoneInfo("GMT")
        name = target_dict["name"]
        active_flag = target_dict["active_flag"]
        width = target_dict["width"]
        image_base64 = target_dict["image_base64"]
        image_value = base64.b64decode(image_base64)
        processing_time_seconds = target_dict["processing_time_seconds"]
        application_metadata = target_dict["application_metadata"]
        target_id = target_dict["target_id"]
        delete_date_optional = target_dict["delete_date_optional"]
        if delete_date_optional is None:
            delete_date = None
        else:
            delete_date = datetime.datetime.fromisoformat(delete_date_optional)
            delete_date = delete_date.replace(tzinfo=timezone)

        last_modified_date = datetime.datetime.fromisoformat(
            target_dict["last_modified_date"],
        ).replace(tzinfo=timezone)
        upload_date = datetime.datetime.fromisoformat(
            target_dict["upload_date"],
        ).replace(tzinfo=timezone)

        target_tracking_rater = HardcodedTargetTrackingRater(
            rating=target_dict["tracking_rating"],
        )
        return Target(
            target_id=target_id,
            name=name,
            active_flag=active_flag,
            width=width,
            image_value=image_value,
            processing_time_seconds=processing_time_seconds,
            application_metadata=application_metadata,
            delete_date=delete_date,
            last_modified_date=last_modified_date,
            upload_date=upload_date,
            target_tracking_rater=target_tracking_rater,
        )

    def to_dict(self) -> TargetDict:
        """
        Dump a target to a dictionary which can be loaded as JSON.
        """
        delete_date: str | None = None
        if self.delete_date:
            delete_date = datetime.datetime.isoformat(self.delete_date)

        image_base64 = base64.encodebytes(self.image_value).decode()

        return {
            "name": self.name,
            "width": self.width,
            "image_base64": image_base64,
            "active_flag": self.active_flag,
            "processing_time_seconds": self.processing_time_seconds,
            "application_metadata": self.application_metadata,
            "target_id": self.target_id,
            "last_modified_date": self.last_modified_date.isoformat(),
            "delete_date_optional": delete_date,
            "upload_date": self.upload_date.isoformat(),
            "tracking_rating": self.tracking_rating,
        }
