"""Validators for given JSON."""

import logging
from collections.abc import Callable
from http import HTTPStatus

from beartype import beartype

from mock_vws._services_validators.context import ValidatorContext
from mock_vws._services_validators.exceptions import (
    BadRequestError,
    FailError,
    UnnecessaryRequestBodyError,
    ValidatorError,
)

_LOGGER = logging.getLogger(name=__name__)


@beartype
def validate_no_body_given(*, context: ValidatorContext) -> None:
    """Validate that no body is given to an endpoint which does not take
    one.

    Args:
        context: The context of the request.

    Raises:
        UnnecessaryRequestBodyError: A request body was given.
    """
    if not bool(context.request_body):
        return

    _LOGGER.warning(
        msg=(
            "A request body was given for an endpoint which does not "
            "require one."
        ),
    )
    raise UnnecessaryRequestBodyError


@beartype
def _validate_json(
    *,
    context: ValidatorContext,
    make_empty_body_error: Callable[[], ValidatorError],
    make_invalid_json_error: Callable[[], ValidatorError],
) -> None:
    """Validate that the given body is a JSON object.

    Args:
        context: The context of the request.
        make_empty_body_error: Create the error to raise if the body is
            empty.
        make_invalid_json_error: Create the error to raise if the body is not
            a JSON object.

    Raises:
        ValidatorError: The request body is empty, is not valid UTF-8, or is
            not a JSON object.
    """
    if not bool(context.request_body):
        _LOGGER.warning(msg="The request body is empty.")
        raise make_empty_body_error()

    # Vuforia gives the same response for a body which is not UTF-8, such as
    # JSON encoded as latin-1, as it gives for a body which is not valid JSON
    # or which is not a JSON object.
    try:
        _ = context.request_json
    except (TypeError, ValueError) as exc:
        _LOGGER.warning(msg="The request body is not a JSON object.")
        raise make_invalid_json_error() from exc


@beartype
def validate_target_json(*, context: ValidatorContext) -> None:
    """Validate the body given to the add and update target endpoints.

    Vuforia reports a server error for an empty body given to these
    endpoints, but a bad request for a body which is not a JSON object.

    Args:
        context: The context of the request.
    """
    _validate_json(
        context=context,
        make_empty_body_error=lambda: FailError(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        ),
        make_invalid_json_error=lambda: FailError(
            status_code=HTTPStatus.BAD_REQUEST,
        ),
    )


@beartype
def validate_reco_counts_report_json(*, context: ValidatorContext) -> None:
    """Validate the body given to the reco counts report endpoint.

    Unlike the target endpoints, this endpoint reports a bad request rather
    than a server error for an empty body.

    Args:
        context: The context of the request.
    """
    _validate_json(
        context=context,
        make_empty_body_error=lambda: FailError(
            status_code=HTTPStatus.BAD_REQUEST,
        ),
        make_invalid_json_error=lambda: FailError(
            status_code=HTTPStatus.BAD_REQUEST,
        ),
    )


@beartype
def validate_vumark_instance_json(*, context: ValidatorContext) -> None:
    """Validate the body given to the VuMark instance generation endpoint.

    That endpoint gives a different error from every other VWS endpoint for
    a body which is empty or which is not a JSON object.

    Args:
        context: The context of the request.
    """
    _validate_json(
        context=context,
        make_empty_body_error=BadRequestError,
        make_invalid_json_error=BadRequestError,
    )
