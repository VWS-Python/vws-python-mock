"""Shared helpers for database summary tests."""

import logging

from beartype import beartype
from tenacity import RetryCallState, retry
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from vws import VWS

from vws_mock_contract_tests.utils.retries import TRANSIENT_VWS_EXCEPTIONS

LOGGER = logging.getLogger(name=__name__)

LOGGER.setLevel(level=logging.DEBUG)


@beartype
def _log_attempt_number(retry_state: RetryCallState) -> None:
    """Log the attempt number of a retry."""
    attempt_number: int = retry_state.attempt_number
    message = f"Attempt number: {attempt_number}"
    LOGGER.debug(msg=message)


@retry(
    # We wait 0.2 seconds rather than less than that to decrease the number
    # of calls made to the API, to decrease the likelihood of hitting the
    # request quota.
    wait=wait_fixed(wait=0.2),
    # Wait up to 700 seconds (arbitrary, though we saw timeouts with 500
    # seconds) for the number of images in various categories to match the
    # expected number. This is necessary because the database summary endpoint
    # lags behind the real data.
    stop=stop_after_delay(max_delay=700),
    # Retry a stale summary, and also retry a poll which fails transiently.
    # ``pytest-retry`` would retry the whole test on a transient failure, but
    # that restarts the 700 second clock and adds another target, so it is
    # better to retry just the one poll which failed.
    retry=retry_if_exception_type(
        exception_types=(AssertionError, *TRANSIENT_VWS_EXCEPTIONS),
    ),
    before=_log_attempt_number,
)
def wait_for_image_numbers(
    *,
    vws_client: VWS,
    active_images: int,
    inactive_images: int,
    failed_images: int,
    processing_images: int,
) -> None:
    """Wait for the number of images in various categories of the database
    summary to match the expected given numbers.

    Args:
        vws_client: The client to use to connect to Vuforia.
        active_images: The expected number of active images.
        inactive_images: The expected number of inactive images.
        failed_images: The expected number of failed images.
        processing_images: The expected number of processing images.

    Raises:
        AssertionError: The numbers of images in various categories do not
            match within the time limit.
        Exception: A request to the real service remains unavailable for the
            full retry period.
    """
    database_summary_report = vws_client.get_database_summary_report()

    expected = {
        "active_images": active_images,
        "inactive_images": inactive_images,
        "failed_images": failed_images,
        "processing_images": processing_images,
    }

    actual = {
        "active_images": database_summary_report.active_images,
        "inactive_images": database_summary_report.inactive_images,
        "failed_images": database_summary_report.failed_images,
        "processing_images": database_summary_report.processing_images,
    }

    msg = f"Expected: {expected}. Actual: {actual}"
    LOGGER.debug(msg=msg)
    assert actual == expected
