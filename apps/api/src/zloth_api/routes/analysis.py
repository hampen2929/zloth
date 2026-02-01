"""API routes for prompt analysis and recommendations."""

from fastapi import APIRouter, Depends, Query

from zloth_api.dependencies import get_analysis_service
from zloth_api.domain.models import (
    AnalysisDetail,
    AnalysisRecommendation,
    AnalysisSummary,
    PromptQualityAnalysis,
)
from zloth_api.services.analysis_service import AnalysisService

router = APIRouter(prefix="/v1/analysis", tags=["analysis"])


@router.get("", response_model=AnalysisDetail)
async def get_analysis(
    period: str = Query("30d", description="Period: 7d, 30d, 90d, all"),
    repo_id: str | None = Query(None, description="Filter by repository ID"),
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisDetail:
    """Get complete analysis detail for a period."""
    return await analysis_service.get_analysis_detail(period, repo_id)


@router.get("/summary", response_model=AnalysisSummary)
async def get_analysis_summary(
    period: str = Query("30d", description="Period: 7d, 30d, 90d, all"),
    repo_id: str | None = Query(None, description="Filter by repository ID"),
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisSummary:
    """Get analysis summary."""
    detail = await analysis_service.get_analysis_detail(period, repo_id)
    return detail.summary


@router.get("/prompts", response_model=PromptQualityAnalysis)
async def get_prompt_analysis(
    period: str = Query("30d", description="Period: 7d, 30d, 90d, all"),
    repo_id: str | None = Query(None, description="Filter by repository ID"),
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> PromptQualityAnalysis:
    """Get prompt quality analysis."""
    detail = await analysis_service.get_analysis_detail(period, repo_id)
    return detail.prompt_analysis


@router.get("/recommendations", response_model=list[AnalysisRecommendation])
async def get_recommendations(
    period: str = Query("30d", description="Period: 7d, 30d, 90d, all"),
    repo_id: str | None = Query(None, description="Filter by repository ID"),
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> list[AnalysisRecommendation]:
    """Get prioritized recommendations."""
    detail = await analysis_service.get_analysis_detail(period, repo_id)
    return detail.recommendations
