"""
Validators for target names.
"""


@wrapt.decorator
def validate_name_characters_in_range(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate the characters in the name argument given to a VWS endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A ``FORBIDDEN`` response if the name is given includes characters
        outside of the accepted range.
    """
    request, context = args

    if not request.text:
        return wrapped(*args, **kwargs)

    if 'name' not in request.json():
        return wrapped(*args, **kwargs)

    name = request.json()['name']

    if all(ord(character) <= 65535 for character in name):
        return wrapped(*args, **kwargs)

    if (request.method, request.path) == ('POST', '/targets'):
        context.status_code = codes.INTERNAL_SERVER_ERROR
        resources_dir = Path(__file__).parent.parent / 'resources'
        filename = 'oops_error_occurred_response.html'
        oops_resp_file = resources_dir / filename
        content_type = 'text/html; charset=UTF-8'
        context.headers['Content-Type'] = content_type
        text = oops_resp_file.read_text()
        return text

    context.status_code = codes.FORBIDDEN
    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.TARGET_NAME_EXIST.value,
    }
    return json_dump(body)


@wrapt.decorator
def validate_name_type(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate the type of the name argument given to a VWS endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `BAD_REQUEST` response if the name is given and not a string.
        is not between 1 and
        64 characters in length.
    """
    request, context = args

    if not request.text:
        return wrapped(*args, **kwargs)

    if 'name' not in request.json():
        return wrapped(*args, **kwargs)

    name = request.json()['name']

    if isinstance(name, str):
        return wrapped(*args, **kwargs)

    context.status_code = codes.BAD_REQUEST
    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.FAIL.value,
    }
    return json_dump(body)


@wrapt.decorator
def validate_name_length(
    wrapped: Callable[..., str],
    instance: Any,  # pylint: disable=unused-argument
    args: Tuple[_RequestObjectProxy, _Context],
    kwargs: Dict,
) -> str:
    """
    Validate the length of the name argument given to a VWS endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A `BAD_REQUEST` response if the name is given is not between 1 and 64
        characters in length.
    """
    request, context = args

    if not request.text:
        return wrapped(*args, **kwargs)

    if 'name' not in request.json():
        return wrapped(*args, **kwargs)

    name = request.json()['name']

    if name and len(name) < 65:
        return wrapped(*args, **kwargs)

    context.status_code = codes.BAD_REQUEST
    body = {
        'transaction_id': uuid.uuid4().hex,
        'result_code': ResultCodes.FAIL.value,
    }
    return json_dump(body)
