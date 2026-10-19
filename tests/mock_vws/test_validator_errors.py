"""Validator errors always carry a complete HTTP response."""

from http import HTTPStatus

import pytest

from mock_vws._query_validators.exceptions import (
    ValidatorError as QueryValidatorError,
)
from mock_vws._services_validators.exceptions import (
    ValidatorError as ServicesValidatorError,
)


@pytest.mark.parametrize(
    argnames="error_type",
    argvalues=[QueryValidatorError, ServicesValidatorError],
    ids=["query", "services"],
)
def test_complete_response(
    error_type: type[QueryValidatorError | ServicesValidatorError],
) -> None:
    """A validator error can be consumed without uninitialized fields."""
    response_text = "Invalid request"
    headers = {
        "Content-Type": "text/plain",
        "Content-Length": str(object=len(response_text)),
    }
    error = error_type(
        status_code=HTTPStatus.BAD_REQUEST,
        response_text=response_text,
        headers=headers,
    )

    assert error.status_code is HTTPStatus.BAD_REQUEST
    assert error.response_text == response_text
    assert error.headers == headers
    assert error.args == ()
