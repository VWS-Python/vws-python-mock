"""Validators for the VWS request rates."""

from beartype import beartype

from mock_vws.database import CloudDatabase

from .context import ValidatorContext


@beartype
def validate_request_rate(*, context: ValidatorContext) -> None:
    """Apply the configured request rates to the matching cloud
    database.

    Args:
        context: The context of the request.
    """
    if isinstance(context.database, CloudDatabase):
        context.request_rate_limiter.validate(
            database=context.database,
            endpoint=context.rate_limited_endpoint,
        )
