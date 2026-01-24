"""Prometheus metrics endpoint for infrastructure monitoring.

This endpoint exposes Prometheus-formatted metrics for scraping by monitoring systems.
"""

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter(tags=["prometheus"])


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    """Expose Prometheus metrics for scraping.

    Returns:
        Prometheus text format metrics.
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
