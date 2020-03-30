"""
A fake implementation of a target for the Vuforia Web Services API.
"""

import base64
import datetime
import io
import random
import statistics
import uuid
from typing import Dict, Optional, Union

import pytz
from PIL import Image, ImageStat

from mock_vws._constants import TargetStatuses


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
        gmt = pytz.timezone('GMT')
        now = datetime.datetime.now(tz=gmt)
        self.upload_date: datetime.datetime = now
        self.last_modified_date = self.upload_date
        self.processed_tracking_rating = random.randint(0, 5)
        self.image = image
        self.reco_rating = ''
        self._processing_time_seconds = processing_time_seconds
        self.application_metadata = application_metadata
        self.delete_date: Optional[datetime.datetime] = None

    def __repr__(self) -> str:
        """
        XXX
        """
        class_name = self.__class__.__name__
        return f'<{class_name}: {self.target_id}>'

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

        gmt = pytz.timezone('GMT')
        now = datetime.datetime.now(tz=gmt)
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
            seconds=self._processing_time_seconds / 2,
        )

        gmt = pytz.timezone('GMT')
        now = datetime.datetime.now(tz=gmt)
        time_since_upload = now - self.upload_date

        if time_since_upload <= pre_rating_time:
            return -1

        if self._post_processing_status == TargetStatuses.SUCCESS:
            return self.processed_tracking_rating

        return 0

    def to_dict(self) -> Dict[str, Optional[Union[str, int, bool, float]]]:
        # TODO e.g. processed tracking rating can surely change if
        # target is dumped then recreated.
        #
        # as can e.g. processing time... maybe use dataclass but then
        # https://github.com/agronholm/sphinx-autodoc-typehints/issues/123
        if self.delete_date:
            delete_date: Optional[str] = datetime.datetime.isoformat(
                self.delete_date,
            )
        else:
            delete_date = None
        return {
            'name': self.name,
            'width': self.width,
            'image_base64':
            base64.encodestring(self.image.getvalue()).decode(),
            'active_flag': self.active_flag,
            'processing_time_seconds': self._processing_time_seconds,
            'application_metadata': self.application_metadata,
            'target_id': self.target_id,
            'last_modified_date': self.last_modified_date.isoformat(),
            'delete_date_optional': delete_date,
            'upload_date': self.upload_date.isoformat(),
        }
