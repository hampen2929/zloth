"""Observability module for zloth API.

This module provides Prometheus metrics, structured logging, and request tracing.
"""

from zloth_api.observability.logging import configure_logging, get_logger
from zloth_api.observability.metrics import (
    GIT_CLONE_DURATION,
    GIT_CLONE_SIZE,
    HTTP_REQUEST_DURATION,
    HTTP_REQUESTS_TOTAL,
    JOB_DURATION,
    JOB_TOTAL,
    LLM_LATENCY,
    LLM_REQUESTS,
    LLM_TOKENS,
    QUEUE_LATENCY,
    QUEUE_SIZE,
)
from zloth_api.observability.middleware import MetricsMiddleware

__all__ = [
    # Logging
    "configure_logging",
    "get_logger",
    # Metrics
    "GIT_CLONE_DURATION",
    "GIT_CLONE_SIZE",
    "HTTP_REQUEST_DURATION",
    "HTTP_REQUESTS_TOTAL",
    "JOB_DURATION",
    "JOB_TOTAL",
    "LLM_LATENCY",
    "LLM_REQUESTS",
    "LLM_TOKENS",
    "QUEUE_LATENCY",
    "QUEUE_SIZE",
    # Middleware
    "MetricsMiddleware",
]
