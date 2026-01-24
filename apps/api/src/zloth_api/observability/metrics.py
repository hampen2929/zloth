"""Prometheus metrics definitions for zloth API.

This module defines all Prometheus metrics used for infrastructure observability.
Metrics follow the naming convention: zloth_<subsystem>_<name>_<unit>

Categories:
- Queue metrics: queue size, latency
- Job metrics: duration, total count by status
- HTTP metrics: request duration, total count
- LLM API metrics: latency, tokens, request counts
- Git metrics: clone duration, size
"""

from prometheus_client import Counter, Gauge, Histogram

# -----------------------------------------------------------------------------
# Queue metrics
# -----------------------------------------------------------------------------

QUEUE_SIZE = Gauge(
    "zloth_queue_size",
    "Current number of jobs in queue",
    ["kind"],
)

QUEUE_LATENCY = Histogram(
    "zloth_queue_latency_seconds",
    "Time jobs spend waiting in queue before processing",
    ["kind"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0),
)

# -----------------------------------------------------------------------------
# Job metrics
# -----------------------------------------------------------------------------

JOB_DURATION = Histogram(
    "zloth_job_duration_seconds",
    "Job execution duration",
    ["kind", "status"],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1800.0, 3600.0),
)

JOB_TOTAL = Counter(
    "zloth_jobs_total",
    "Total number of jobs processed",
    ["kind", "status"],
)

# -----------------------------------------------------------------------------
# HTTP request metrics
# -----------------------------------------------------------------------------

HTTP_REQUEST_DURATION = Histogram(
    "zloth_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint", "status_code"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

HTTP_REQUESTS_TOTAL = Counter(
    "zloth_http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"],
)

# -----------------------------------------------------------------------------
# LLM API metrics
# -----------------------------------------------------------------------------

LLM_REQUESTS = Counter(
    "zloth_llm_requests_total",
    "Total LLM API requests",
    ["provider", "status"],
)

LLM_LATENCY = Histogram(
    "zloth_llm_latency_seconds",
    "LLM API request latency",
    ["provider"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0),
)

LLM_TOKENS = Counter(
    "zloth_llm_tokens_total",
    "Total LLM tokens used",
    ["provider", "direction"],  # direction: input or output
)

# -----------------------------------------------------------------------------
# Git operation metrics
# -----------------------------------------------------------------------------

GIT_CLONE_DURATION = Histogram(
    "zloth_git_clone_seconds",
    "Git clone operation duration",
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0),
)

GIT_CLONE_SIZE = Histogram(
    "zloth_git_clone_bytes",
    "Git clone size in bytes",
    buckets=(
        1024 * 1024,  # 1 MB
        10 * 1024 * 1024,  # 10 MB
        50 * 1024 * 1024,  # 50 MB
        100 * 1024 * 1024,  # 100 MB
        500 * 1024 * 1024,  # 500 MB
        1024 * 1024 * 1024,  # 1 GB
    ),
)
