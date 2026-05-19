"""Support callables for the strict-kwargs stress fixture."""

from __future__ import annotations

from dataclasses import dataclass


def first_party_function(a: int, b: int = 0) -> int:
    """Return the sum of two integers."""
    return a + b


def positional_only(value: int, /) -> int:
    """Return the positional-only value."""
    return value


class Service:
    """Service with representative method shapes."""

    def __init__(self, name: str) -> None:
        """Initialize the service."""
        self.name = name

    def method(self, item: int) -> int:
        """Return an instance-method item."""
        return item

    @classmethod
    def class_method(cls, item: int) -> int:
        """Return a class-method item."""
        return item

    @staticmethod
    def static_method(item: int) -> int:
        """Return a static-method item."""
        return item


@dataclass
class Data:
    """Simple dataclass with a synthesized constructor."""

    name: str
