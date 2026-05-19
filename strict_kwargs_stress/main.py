"""Call-site stress cases for strict-kwargs."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import NewType, ParamSpec, TypeAliasType, TypeVar, TypeVarTuple

from strict_kwargs_stress.pkg.lib import (
    Data,
    Service,
    first_party_function,
    positional_only,
)

_P = ParamSpec("_P")
_T = TypeVar("_T")
_Ts = TypeVarTuple("_Ts")  # noqa: PYI018
UserId = NewType("UserId", int)
Vector = TypeAliasType("Vector", list[int])  # noqa: UP040
_VECTOR_SAMPLE: Vector = []


def _preserve_signature(func: Callable[_P, _T]) -> Callable[_P, _T]:  # noqa: UP047
    """Return the given callable with its ParamSpec signature
    preserved.
    """
    return func


@_preserve_signature
def _sample(value: int) -> int:
    """Return a sample value for exercising the ParamSpec helper."""
    return value


def _accept_user_id(user_id: UserId) -> UserId:
    """Return a sample ``NewType`` value."""
    return user_id


_SAMPLE_RESULT = _sample(value=1)
_USER_ID_VALUE = UserId(1)  # type: ignore[misc]
_USER_ID = _accept_user_id(user_id=_USER_ID_VALUE)


type _Packed[*_Ts] = tuple[*_Ts]  # noqa: PYI047

first_party_function(a=1, b=2)  # type: ignore[misc]
first_party_function(a=1, b=2)
positional_only(1)

Service(name="svc")  # type: ignore[misc]
Service(name="svc").method(3)  # type: ignore[misc]
service = Service(name="svc")
service.method(item=7)  # type: ignore[misc]
Service.method(Service(name="svc"), item=4)  # type: ignore[misc]
Service.method(Service(name="svc"), item=4)  # type: ignore[misc]
Service.class_method(item=5)  # type: ignore[misc]
Service.static_method(item=6)  # type: ignore[misc]
Data("name")  # type: ignore[misc]

sys.stdout.write("ok\n")
str.lower("ABC")
