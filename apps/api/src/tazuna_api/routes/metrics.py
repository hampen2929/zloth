"""API routes for development metrics."""

from fastapi import APIRouter, Depends, Query

from tazuna_api.dependencies import get_metrics_service
from tazuna_api.domain.models import (
    MetricsDetail,
    MetricsSummary,
    MetricsTrend,
    RealtimeMetrics,
)
from tazuna_api.services.metrics_service import MetricsService

router = APIRouter(prefix="/v1/metrics", tags=["metrics"])


@router.get("", response_model=MetricsDetail)
async def get_metrics(
    period: str = Query("30d", description="Period: 1d, 7d, 30d, 90d, all"),
    repo_id: str | None = Query(None, description="Filter by repository ID"),
    metrics_service: MetricsService = Depends(get_metrics_service),
) -> MetricsDetail:
    """Get complete metrics detail for a period."""
    return await metrics_service.get_metrics_detail(period, repo_id)


@router.get("/summary", response_model=MetricsSummary)
async def get_metrics_summary(
    period: str = Query("7d", description="Period: 1d, 7d, 30d, 90d, all"),
    repo_id: str | None = Query(None, description="Filter by repository ID"),
    metrics_service: MetricsService = Depends(get_metrics_service),
) -> MetricsSummary:
    """Get a summary of key metrics."""
    return await metrics_service.get_summary(period, repo_id)


@router.get("/realtime", response_model=RealtimeMetrics)
async def get_realtime_metrics(
    repo_id: str | None = Query(None, description="Filter by repository ID"),
    metrics_service: MetricsService = Depends(get_metrics_service),
) -> RealtimeMetrics:
    """Get current real-time metrics."""
    return await metrics_service.get_realtime(repo_id)


@router.get("/trends", response_model=list[MetricsTrend])
async def get_metrics_trends(
    metrics: list[str] = Query(
        ["merge_rate", "run_success_rate", "throughput"],
        description="Metric names to include",
    ),
    period: str = Query("30d", description="Period: 1d, 7d, 30d, 90d, all"),
    granularity: str = Query("day", description="Granularity: hour, day, week"),
    repo_id: str | None = Query(None, description="Filter by repository ID"),
    metrics_service: MetricsService = Depends(get_metrics_service),
) -> list[MetricsTrend]:
    """Get trend data for specified metrics."""
    return await metrics_service.get_trends(metrics, period, granularity, repo_id)
