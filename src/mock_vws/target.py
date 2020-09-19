"""
A fake implementation of a target for the Vuforia Web Services API.
"""
from __future__ import annotations

import base64
import datetime
import io
import random
import statistics
import uuid
from typing import Optional, TypedDict, Union

from backports.zoneinfo import ZoneInfo
from PIL import Image, ImageStat

from mock_vws._constants import TargetStatuses


class TargetDict(TypedDict):
    name: str
    width: float
    image_base64: str
    active_flag: bool
    processing_time_seconds: Union[int, float]
    processed_tracking_rating: int
    application_metadata: str
    target_id: str
    last_modified_date: str
    delete_date_optional: Optional[str]
    upload_date: str


class Target:  # pylint: disable=too-many-instance-attributes
    """
    A Vuforia Target as managed in
    https://developer.vuforia.com/target-manager.
    """

    name: str
    target_id: str
    active_flag: bool
    width: float
    upload_date: datetime.datetime
    last_modified_date: datetime.datetime
    processed_tracking_rating: int
    image: io.BytesIO
    reco_rating: str
    application_metadata: str
    delete_date: Optional[datetime.datetime]

    def __init__(  # pylint: disable=too-many-arguments
        self,
        name: str,
        active_flag: bool,
        width: float,
        image: io.BytesIO,
        processing_time_seconds: Union[int, float],
        application_metadata: str,
    ) -> None:
        """
        Args:
            name: The name of the target.
            active_flag: Whether or not the target is active for query.
            width: The width of the image in scene unit.
            image: The image associated with the target.
            processing_time_seconds: The number of seconds to process each
                image for. In the real Vuforia Web Services, this is not
                deterministic.
            application_metadata: The base64 encoded application metadata
                associated with the target.

        Attributes:
            name (str): The name of the target.
            target_id (str): The unique ID of the target.
            active_flag (bool): Whether or not the target is active for query.
            width (float): The width of the image in scene unit.
            upload_date (datetime.datetime): The time that the target was
                created.
            last_modified_date (datetime.datetime): The time that the target
                was last modified.
            processed_tracking_rating (int): The tracking rating of the target
                once it has been processed.
            image (io.BytesIO): The image data associated with the target.
            reco_rating (str): An empty string ("for now" according to
                Vuforia's documentation).
            application_metadata (str): The base64 encoded application metadata
                associated with the target.
            delete_date (typing.Optional[datetime.datetime]): The time that the
                target was deleted.
        """
        self.name = name
        self.target_id = uuid.uuid4().hex
        self.active_flag = active_flag
        self.width = width
        self._timezone = ZoneInfo('GMT')
        now = datetime.datetime.now(tz=self._timezone)
        self.upload_date: datetime.datetime = now
        self.last_modified_date = self.upload_date
        self.processed_tracking_rating = random.randint(0, 5)
        self.image = image
        self.reco_rating = ''
        self._processing_time_seconds = processing_time_seconds
        self.application_metadata = application_metadata
        self.delete_date: Optional[datetime.datetime] = None
        self.total_recos: int = 0
        self.current_month_recos: int = 0
        self.previous_month_recos: int = 0

    def __repr__(self) -> str:
        """
        Return a representation which includes the target ID.
        """
        class_name = self.__class__.__name__
        return f'<{class_name}: {self.target_id}>'

    def delete(self) -> None:
        """
        Mark the target as deleted.
        """
        now = datetime.datetime.now(tz=self._timezone)
        self.delete_date = now

    @property
    def _post_processing_status(self) -> TargetStatuses:
        """
        Return the status of the target, or what it will be when processing is
        finished.

        The status depends on the standard deviation of the color bands.
        How VWS determines this is unknown, but it relates to how suitable the
        target is for detection.
        """
        image = Image.open(self.image)
        image_stat = ImageStat.Stat(image)

        average_std_dev = statistics.mean(image_stat.stddev)

        if average_std_dev > 5:
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
            seconds=self._processing_time_seconds,
        )

        now = datetime.datetime.now(tz=self._timezone)
        time_since_change = now - self.last_modified_date

        if time_since_change <= processing_time:
            return str(TargetStatuses.PROCESSING.value)

        return str(self._post_processing_status.value)

    @property
    def tracking_rating(self) -> int:
        """
        Return the tracking rating of the target recognition image.

        In this implementation that is just a random integer between 0 and 5
        if the target status is 'success'.
        The rating is 0 if the target status is 'failed'.
        The rating is -1 for a short time while the target is being processed.
        The real VWS seems to give -1 for a short time while processing, then
        the real rating, even while it is still processing.
        """
        pre_rating_time = datetime.timedelta(
            # That this is half of the total processing time is unrealistic.
            # In VWS it is not a constant percentage.
            seconds=self._processing_time_seconds
            / 2,
        )

        now = datetime.datetime.now(tz=self._timezone)
        time_since_upload = now - self.upload_date

        if time_since_upload <= pre_rating_time:
            return -1

        if self._post_processing_status == TargetStatuses.SUCCESS:
            return self.processed_tracking_rating

        return 0

    @classmethod
    def from_dict(cls, target_dict: TargetDict) -> Target:
        """
        Load a target from a dictionary.
        """
        name = target_dict['name']
        active_flag = target_dict['active_flag']
        width = target_dict['width']
        image_base64 = target_dict['image_base64']
        upload_date = target_dict['upload_date']
        processed_tracking_rating = target_dict['processed_tracking_rating']
        image_bytes = base64.b64decode(image_base64)
        image = io.BytesIO(image_bytes)
        processing_time_seconds = target_dict['processing_time_seconds']
        application_metadata = target_dict['application_metadata']

        target = Target(
            name=name,
            active_flag=active_flag,
            width=width,
            image=image,
            processing_time_seconds=processing_time_seconds,
            application_metadata=application_metadata,
        )
        target.target_id = target_dict['target_id']
        gmt = ZoneInfo('GMT')
        target.last_modified_date = datetime.datetime.fromisoformat(
            target_dict['last_modified_date'],
        ).replace(tzinfo=gmt)
        target.upload_date = datetime.datetime.fromisoformat(upload_date)
        target.processed_tracking_rating = processed_tracking_rating
        target.upload_date = target.upload_date.replace(tzinfo=gmt)
        delete_date_optional = target_dict['delete_date_optional']
        if delete_date_optional:
            target.delete_date = datetime.datetime.fromisoformat(
                delete_date_optional,
            ).replace(tzinfo=gmt)
        return target

    def to_dict(self) -> TargetDict:
        delete_date: Optional[str] = None
        if self.delete_date:
            delete_date = datetime.datetime.isoformat(self.delete_date)

        image_value = self.image.getvalue()
        image_base64 = base64.encodebytes(image_value).decode()

        return {
            'name': self.name,
            'width': self.width,
            'image_base64': image_base64,
            'active_flag': self.active_flag,
            'processing_time_seconds': self._processing_time_seconds,
            'processed_tracking_rating': self.processed_tracking_rating,
            'application_metadata': self.application_metadata,
            'target_id': self.target_id,
            'last_modified_date': self.last_modified_date.isoformat(),
            'delete_date_optional': delete_date,
            'upload_date': self.upload_date.isoformat(),
        }
