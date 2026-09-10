"""Validators for target names."""

import logging
from http import HTTPStatus

from beartype import beartype
from pydantic import TypeAdapter

from mock_vws._services_validators.context import ValidatorContext
from mock_vws._services_validators.exceptions import (
    FailError,
    TargetNameExistError,
)
from mock_vws._services_validators.target_validators import (
    target_id_from_path,
)
from mock_vws.target import ImageTarget, VuMarkTarget

_LOGGER = logging.getLogger(name=__name__)

_MAX_CHARACTER_ORD = 65535
_OPTIONAL_NAME_ADAPTER: TypeAdapter[str | None] = TypeAdapter(type=str | None)
_NAME_ADAPTER: TypeAdapter[str] = TypeAdapter(type=str)


@beartype
def _given_name(*, context: ValidatorContext) -> str | None:
    """Return the name given in the request body.

    Args:
        context: The context of the request.

    Returns:
        The value of the ``name`` field, or ``None`` if no name was given.
        The value has already been checked to be a string by
        :py:func:`validate_name_type`.
    """
    return _OPTIONAL_NAME_ADAPTER.validate_python(
        context.request_json.get("name"),
        strict=True,
    )


@beartype
def _name_characters_in_range(*, name: str) -> bool:
    """Whether every character in a name is in the range Vuforia accepts.

    Args:
        name: The name given in the request body.

    Returns:
        Whether every character in the name is in range.
    """
    return all(ord(character) <= _MAX_CHARACTER_ORD for character in name)


@beartype
def _new_target_name(*, context: ValidatorContext) -> str:
    """Return the name given when adding a target.

    Args:
        context: The context of the request.

    Returns:
        The value of the ``name`` field. ``name`` is a mandatory key on the
        add target endpoint, so :py:func:`validate_keys` has already rejected
        a request which does not give one, and :py:func:`validate_name_type`
        has already rejected one which is not a string.
    """
    return _NAME_ADAPTER.validate_python(
        context.request_json["name"],
        strict=True,
    )


@beartype
def _targets_with_name(
    *,
    context: ValidatorContext,
    name: str,
) -> list[ImageTarget | VuMarkTarget]:
    """Return the targets in the database which have the given name.

    Args:
        context: The context of the request.
        name: The name to look for.

    Returns:
        Every target which is not deleted and which has the given name.
    """
    return [
        target
        for target in context.database.not_deleted_targets
        if target.name == name
    ]


@beartype
def validate_new_target_name_characters_in_range(
    *,
    context: ValidatorContext,
) -> None:
    """Validate the characters in the name given when adding a target.

    Args:
        context: The context of the request.

    Raises:
        FailError: Characters are out of range.
    """
    if _name_characters_in_range(name=_new_target_name(context=context)):
        return

    _LOGGER.warning(msg="Characters are out of range.")
    raise FailError(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)


@beartype
def validate_existing_target_name_characters_in_range(
    *,
    context: ValidatorContext,
) -> None:
    """Validate the characters in the name given when updating a target.

    Args:
        context: The context of the request.

    Raises:
        TargetNameExistError: Characters are out of range.
    """
    name = _given_name(context=context)
    if name is None or _name_characters_in_range(name=name):
        return

    _LOGGER.warning(msg="Characters are out of range.")
    raise TargetNameExistError


@beartype
def validate_name_type(*, context: ValidatorContext) -> None:
    """Validate the type of the name argument given to a VWS endpoint.

    Args:
        context: The context of the request.

    Raises:
        FailError: A name is given and it is not a string.
    """
    request_json = context.request_json
    if "name" not in request_json:
        return

    if isinstance(request_json["name"], str):
        return

    _LOGGER.warning(msg="Name is not a string.")
    raise FailError(status_code=HTTPStatus.BAD_REQUEST)


@beartype
def validate_name_length(*, context: ValidatorContext) -> None:
    """Validate the length of the name argument given to a VWS endpoint.

    Args:
        context: The context of the request.

    Raises:
        FailError: A name is given and it is not a between 1 and 64 characters
            in length.
    """
    name = _given_name(context=context)
    if name is None:
        return

    max_length = 64
    if len(name) > 0 and len(name) <= max_length:
        return

    _LOGGER.warning(msg="Name is not between 1 and 64 characters in length.")
    raise FailError(status_code=HTTPStatus.BAD_REQUEST)


@beartype
def validate_name_does_not_exist_new_target(
    *,
    context: ValidatorContext,
) -> None:
    """Validate that the name does not exist for any existing target.

    Args:
        context: The context of the request.

    Raises:
        TargetNameExistError: The target name already exists.
    """
    name = _new_target_name(context=context)
    if not bool(_targets_with_name(context=context, name=name)):
        return

    _LOGGER.warning(msg="Target name already exists.")
    raise TargetNameExistError


@beartype
def validate_name_does_not_exist_existing_target(
    *,
    context: ValidatorContext,
) -> None:
    """Validate that the name does not exist for any existing target apart
    from
    the one being updated.

    Args:
        context: The context of the request.

    Raises:
        TargetNameExistError: The target name is not the same as the name of
            the target being updated but it is the same as another target.
    """
    name = _given_name(context=context)
    if name is None:
        return

    matching_name_targets = _targets_with_name(context=context, name=name)
    if not bool(matching_name_targets):
        return

    (matching_name_target,) = matching_name_targets
    if matching_name_target.target_id == target_id_from_path(
        request_path=context.request_path,
    ):
        return

    _LOGGER.warning(msg="Name already exists for another target.")
    raise TargetNameExistError
