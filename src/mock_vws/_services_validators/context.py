"""The request context which every services validator is given."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cached_property
from typing import Any, TypeIs

from beartype import beartype

from mock_vws._base64_decoding import decode_base64
from mock_vws._database_matchers import AnyDatabase
from mock_vws.request_rate_limits import RateLimitedEndpoint

from .request_rate_limiter import RequestRateLimiter


@beartype
def _is_json_object(value: object, /) -> TypeIs[dict[str, Any]]:
    """Return whether a decoded JSON value is an object.

    JSON object keys are always strings, so a ``dict`` from ``json.loads``
    is a ``dict[str, Any]``.
    """
    return isinstance(value, dict)


@beartype
@dataclass(frozen=True, kw_only=True)
class ValidatorContext:
    """Everything which a services validator is given.

    A validator is chosen by the route it belongs to, so it never has to
    work out whether it applies to the request. The route's own facts are
    copied onto the context rather than being looked up again from the
    path and the method.

    The parsed forms of the body are computed the first time a validator
    asks for them and then shared by every validator in the chain, so the
    body is parsed once per request rather than once per validator.

    Args:
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        database: The database which the request's server keys belong to.
        request_rate_limiter: The rate limiter tracking recent requests.
        mandatory_keys: Keys which the route requires in the request body.
        optional_keys: Keys which the route allows in the request body.
        rate_limited_endpoint: The group of endpoints which the route shares
            a request rate limit with.
        allowed_for_inactive_cloud_project: Whether the route works against
            an inactive cloud database.

    Attributes:
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        database: The database which the request's server keys belong to.
        request_rate_limiter: The rate limiter tracking recent requests.
        mandatory_keys: Keys which the route requires in the request body.
        optional_keys: Keys which the route allows in the request body.
        rate_limited_endpoint: The group of endpoints which the route shares
            a request rate limit with.
        allowed_for_inactive_cloud_project: Whether the route works against
            an inactive cloud database.
    """

    request_path: str
    request_headers: Mapping[str, str]
    request_body: bytes
    database: AnyDatabase
    request_rate_limiter: RequestRateLimiter
    mandatory_keys: frozenset[str]
    optional_keys: frozenset[str]
    rate_limited_endpoint: RateLimitedEndpoint
    allowed_for_inactive_cloud_project: bool

    @cached_property
    def request_json(self) -> dict[str, Any]:
        """The request body parsed as a JSON object.

        A route's JSON validator runs before any validator which reads this,
        so by the time a validator does read it, the body is known to be a
        JSON object.

        Raises:
            ValueError: The body is not UTF-8 or is not JSON. Both
                :py:class:`json.JSONDecodeError` and
                :py:class:`UnicodeDecodeError` are kinds of this.
            TypeError: The body is JSON but is not a JSON object.
        """
        parsed: object = json.loads(
            s=self.request_body.decode(encoding="utf-8"),
        )
        if not _is_json_object(parsed):
            msg = "The request body is not a JSON object."
            raise TypeError(msg)
        return parsed

    @cached_property
    def decoded_image(self) -> bytes | None:
        """The base64 decoded image given in the request body, or ``None``
        if no image was given.

        The image data type and encoding validators run before any validator
        which reads this, so by the time a validator does read it, the image
        is known to be a base64 string.

        Raises:
            binascii.Error: The image cannot be base64 decoded.
        """
        image = self.request_json.get("image")
        if image is None:
            return None
        return decode_base64(encoded_data=image)
