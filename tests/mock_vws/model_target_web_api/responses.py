"""Response types and parsing for Model Target Web API tests."""

from typing import TypedDict

import requests
from beartype import beartype
from pydantic import TypeAdapter
from vws.response import Response

from mock_vws.model_target import JSONValue


class ErrorDetail(TypedDict):
    """A validation detail in a Model Target API error response."""

    code: str
    message: str


class Error(TypedDict):
    """The error object in a Model Target API response."""

    code: str
    message: str


class TargetedError(Error):
    """An API error which identifies the failed target."""

    target: str


class ValidationError(TargetedError):
    """An API validation error with field-level details."""

    details: list[ErrorDetail]


class TargetedErrorResponse(TypedDict):
    """A targeted Model Target API error response."""

    error: TargetedError


class ValidationErrorResponse(TypedDict):
    """A Model Target API validation error response."""

    error: ValidationError


@beartype
def parse_response_json(
    *,
    response: requests.Response | Response,
) -> dict[str, JSONValue]:
    """Validate and return a JSON object response."""
    return TypeAdapter(type=dict[str, JSONValue]).validate_json(response.text)


@beartype
def response_targeted_error(
    *,
    response: requests.Response | Response,
) -> TargetedError:
    """Validate and return a targeted Model Target API error response."""
    body = TypeAdapter(type=TargetedErrorResponse).validate_json(
        response.text,
    )
    return body["error"]


@beartype
def response_validation_error(
    *,
    response: requests.Response | Response,
) -> ValidationError:
    """Validate and return a Model Target API validation error
    response.
    """
    body = TypeAdapter(type=ValidationErrorResponse).validate_json(
        response.text,
    )
    return body["error"]
