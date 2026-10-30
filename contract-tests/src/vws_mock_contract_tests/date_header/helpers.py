"""Shared helpers for date header tests."""

from datetime import timedelta

VWS_MAX_TIME_SKEW = timedelta(minutes=5)
LEEWAY = timedelta(seconds=10)
