"""Compatibility imports for the packaged contract suite."""

from vws_mock_test_backends.real_model_target_retries import (
    MODEL_TARGET_RETRY_ATTEMPTS,
    REAL_MODEL_TARGET_RETRY_POLICY,
)

__all__ = ["MODEL_TARGET_RETRY_ATTEMPTS", "REAL_MODEL_TARGET_RETRY_POLICY"]
