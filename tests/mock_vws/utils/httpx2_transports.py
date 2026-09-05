"""``vws-python`` transports which use ``httpx2``.

``vws-python`` ships ``requests`` and ``httpx`` transports. Its ``httpx2``
transports are not released yet, so these stand in for them, and they are
what the tests use to show that ``vws-python`` clients work against the
mock over ``httpx2``.
"""

import httpx2
from beartype import BeartypeConf, beartype
from vws.response import Response


@beartype
def _httpx2_timeout(
    *,
    request_timeout: float | tuple[float, float],
) -> httpx2.Timeout:
    """The ``httpx2`` timeout for a ``vws-python`` request timeout.

    Args:
        request_timeout: The timeout for the request. A float sets both the
            connect and read timeouts. A ``(connect, read)`` tuple sets them
            individually.

    Returns:
        The equivalent ``httpx2`` timeout.
    """
    match request_timeout:
        case tuple() as timeout:
            connect_timeout, read_timeout = timeout
        case timeout:
            connect_timeout = timeout
            read_timeout = timeout

    return httpx2.Timeout(
        connect=connect_timeout,
        read=read_timeout,
        write=None,
        pool=None,
    )


@beartype
def _to_vws_response(*, httpx2_response: httpx2.Response) -> Response:
    """Convert an ``httpx2`` response to a ``vws-python`` response.

    Args:
        httpx2_response: The response to convert.

    Returns:
        The equivalent ``vws-python`` response.
    """
    content = bytes(httpx2_response.content)
    request_content = httpx2_response.request.content

    return Response(
        text=httpx2_response.text,
        url=str(object=httpx2_response.url),
        status_code=httpx2_response.status_code,
        headers=dict(httpx2_response.headers),
        request_body=bytes(request_content) or None,
        tell_position=len(content),
        content=content,
    )


@beartype(conf=BeartypeConf(is_pep484_tower=True))
class HTTPX2Transport:
    """A synchronous ``vws-python`` transport which uses ``httpx2``."""

    def __init__(self) -> None:
        """Create an ``HTTPX2Transport``."""
        self._client = httpx2.Client()

    def close(self) -> None:
        """Close the underlying ``httpx2.Client``."""
        self._client.close()

    def __call__(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        data: bytes,
        request_timeout: float | tuple[float, float],
    ) -> Response:
        """Make an HTTP request using ``httpx2``.

        Args:
            method: The HTTP method.
            url: The full URL.
            headers: Request headers.
            data: The request body.
            request_timeout: The request timeout.

        Returns:
            A response populated from the ``httpx2`` response.
        """
        httpx2_response = self._client.request(
            method=method,
            url=url,
            headers=headers,
            content=data,
            timeout=_httpx2_timeout(request_timeout=request_timeout),
            follow_redirects=True,
        )
        return _to_vws_response(httpx2_response=httpx2_response)


@beartype(conf=BeartypeConf(is_pep484_tower=True))
class AsyncHTTPX2Transport:
    """An asynchronous ``vws-python`` transport which uses ``httpx2``."""

    def __init__(self) -> None:
        """Create an ``AsyncHTTPX2Transport``."""
        self._client = httpx2.AsyncClient()

    async def aclose(self) -> None:
        """Close the underlying ``httpx2.AsyncClient``."""
        await self._client.aclose()

    async def __call__(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        data: bytes,
        request_timeout: float | tuple[float, float],
    ) -> Response:
        """Make an asynchronous HTTP request using ``httpx2``.

        Args:
            method: The HTTP method.
            url: The full URL.
            headers: Request headers.
            data: The request body.
            request_timeout: The request timeout.

        Returns:
            A response populated from the ``httpx2`` response.
        """
        httpx2_response = await self._client.request(
            method=method,
            url=url,
            headers=headers,
            content=data,
            timeout=_httpx2_timeout(request_timeout=request_timeout),
            follow_redirects=True,
        )
        return _to_vws_response(httpx2_response=httpx2_response)
