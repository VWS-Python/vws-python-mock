"""Shared helpers for target summary tests."""

import io

from tenacity import retry
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt
from vws import VWS
from vws.reports import TargetSummaryReport


@retry(
    # The real VWS reports a tracking rating of -1 for only a short time
    # after an upload, and then the image's rating, even while the target
    # is still processing. The window was observed as roughly one second
    # of a roughly thirty second processing time, and a single poll
    # straight after the upload can miss it (see
    # https://github.com/VWS-Python/vws-python-mock/issues/3354).
    #
    # A rating never returns to -1 once it has left it, so polling the
    # same target again is no use. Instead we retry the whole upload and
    # first poll, with a fresh target each time, until we catch the
    # window. This does not make the assertion certain, only unlikely to
    # fail: the window may sometimes be shorter than one round trip.
    #
    # ``pytest-retry`` does not retry ``AssertionError`` in this suite,
    # so the retry lives here.
    stop=stop_after_attempt(max_attempt_number=5),
    retry=retry_if_exception_type(exception_types=(AssertionError,)),
    reraise=True,
)
def add_target_and_get_pre_rating_summary(
    *,
    vws_client: VWS,
    name: str,
    image_file: io.BytesIO,
    active_flag: bool,
) -> TargetSummaryReport:
    """Add a target and return its summary report from before it has a
    tracking rating.

    Args:
        vws_client: The client to use to connect to Vuforia.
        name: The name of the target to add.
        image_file: The image to add.
        active_flag: Whether the target should be active.

    Returns:
        The summary report which was taken while the tracking rating
        was still -1.

    Raises:
        AssertionError: The tracking rating was not -1 on any attempt.
    """
    target_id = vws_client.add_target(
        name=name,
        width=1,
        image=image_file,
        active_flag=active_flag,
        application_metadata=None,
    )

    report = vws_client.get_target_summary_report(target_id=target_id)
    # While processing the tracking rating is -1.
    assert report.tracking_rating == -1
    return report
