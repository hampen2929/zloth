"""Service for analyzing user prompts and generating recommendations."""

from datetime import datetime, timedelta

from zloth_api.domain.enums import ExecutorType
from zloth_api.domain.models import (
    AnalysisDetail,
    AnalysisRecommendation,
    AnalysisSummary,
    ErrorPattern,
    ExecutorSuccessRate,
    PromptQualityAnalysis,
)
from zloth_api.storage.dao import AnalysisDAO


def _parse_period(period: str) -> tuple[datetime, datetime]:
    """Parse period string into start and end datetimes."""
    now = datetime.utcnow()
    period_end = now

    if period == "all":
        period_start = datetime(2020, 1, 1)
    elif period.endswith("d"):
        days = int(period[:-1])
        period_start = now - timedelta(days=days)
    elif period.endswith("w"):
        weeks = int(period[:-1])
        period_start = now - timedelta(weeks=weeks)
    else:
        period_start = now - timedelta(days=30)

    return period_start, period_end


class AnalysisService:
    """Service for analyzing prompts and generating recommendations."""

    def __init__(self, analysis_dao: AnalysisDAO):
        self.analysis_dao = analysis_dao

    async def get_analysis_detail(
        self,
        period: str = "30d",
        repo_id: str | None = None,
    ) -> AnalysisDetail:
        """Get complete analysis detail for a period."""
        period_start, period_end = _parse_period(period)

        # Gather all analysis data
        prompt_data = await self.analysis_dao.get_prompt_analysis(period_start, period_end, repo_id)
        executor_data = await self.analysis_dao.get_executor_success_rates(
            period_start, period_end, repo_id
        )
        error_data = await self.analysis_dao.get_error_patterns(period_start, period_end, repo_id)
        iteration_data = await self.analysis_dao.get_iteration_metrics(
            period_start, period_end, repo_id
        )
        success_rate = await self.analysis_dao.get_success_rate(period_start, period_end, repo_id)

        # Build analysis components
        prompt_analysis = self._build_prompt_analysis(prompt_data)
        executor_success_rates = self._build_executor_success_rates(executor_data)
        error_patterns = self._build_error_patterns(error_data)
        recommendations = self._generate_recommendations(
            prompt_analysis, executor_success_rates, error_patterns, iteration_data
        )

        # Calculate prompt quality score
        prompt_quality_score = self._calculate_prompt_quality_score(prompt_analysis)

        # Build summary
        summary = AnalysisSummary(
            period=period,
            period_start=period_start,
            period_end=period_end,
            prompt_quality_score=prompt_quality_score,
            overall_success_rate=success_rate,
            avg_iterations=iteration_data["avg_iterations"],
            total_tasks_analyzed=iteration_data["total_tasks"],
        )

        return AnalysisDetail(
            summary=summary,
            prompt_analysis=prompt_analysis,
            executor_success_rates=executor_success_rates,
            error_patterns=error_patterns,
            recommendations=recommendations,
        )

    def _build_prompt_analysis(self, data: dict) -> PromptQualityAnalysis:
        """Build prompt quality analysis from raw data."""
        total = data["total_prompts"]

        # Calculate scores
        specificity_score = 0.0
        context_score = 0.0

        if total > 0:
            # Specificity based on file references
            specificity_score = min(100, (data["prompts_with_file_refs"] / total) * 100)

            # Context based on word count (optimal: 30-100 words)
            avg_words = data["avg_word_count"]
            if avg_words < 10:
                context_score = 30.0
            elif avg_words < 30:
                context_score = 50.0
            elif avg_words <= 100:
                context_score = 80.0
            else:
                context_score = 70.0  # Too verbose

        # Determine common missing elements
        missing_elements = []
        if total > 0:
            file_ref_ratio = data["prompts_with_file_refs"] / total
            test_req_ratio = data["prompts_with_test_req"] / total

            if file_ref_ratio < 0.3:
                missing_elements.append("affected_files")
            if test_req_ratio < 0.2:
                missing_elements.append("test_requirements")
            if data["avg_word_count"] < 20:
                missing_elements.append("detailed_context")
            if data["avg_word_count"] < 15:
                missing_elements.append("acceptance_criteria")

        return PromptQualityAnalysis(
            avg_length=data["avg_length"],
            avg_word_count=data["avg_word_count"],
            specificity_score=specificity_score,
            context_score=context_score,
            prompts_with_file_refs=data["prompts_with_file_refs"],
            prompts_with_test_req=data["prompts_with_test_req"],
            total_prompts_analyzed=total,
            common_missing_elements=missing_elements,
        )

    def _build_executor_success_rates(self, data: list[dict]) -> list[ExecutorSuccessRate]:
        """Build executor success rates from raw data."""
        results = []
        for item in data:
            try:
                executor_type = ExecutorType(item["executor_type"])
                total = item["total_runs"]
                success_rate = (item["succeeded_runs"] / total * 100) if total > 0 else 0.0

                results.append(
                    ExecutorSuccessRate(
                        executor_type=executor_type,
                        total_runs=total,
                        succeeded_runs=item["succeeded_runs"],
                        success_rate=success_rate,
                        avg_duration_seconds=item["avg_duration_seconds"],
                    )
                )
            except ValueError:
                pass

        return results

    def _build_error_patterns(self, data: list[dict]) -> list[ErrorPattern]:
        """Build error patterns from raw data."""
        return [
            ErrorPattern(
                pattern=item["pattern"],
                count=item["count"],
                failure_rate=item["failure_rate"],
                affected_files=item["affected_files"],
            )
            for item in data
        ]

    def _calculate_prompt_quality_score(self, prompt_analysis: PromptQualityAnalysis) -> float:
        """Calculate overall prompt quality score (0-100)."""
        if prompt_analysis.total_prompts_analyzed == 0:
            return 0.0

        # Weighted average of various factors
        weights = {
            "specificity": 0.3,
            "context": 0.3,
            "test_inclusion": 0.2,
            "file_refs": 0.2,
        }

        total = prompt_analysis.total_prompts_analyzed
        test_score = min(100, (prompt_analysis.prompts_with_test_req / total) * 100)
        file_score = min(100, (prompt_analysis.prompts_with_file_refs / total) * 100)

        score = (
            prompt_analysis.specificity_score * weights["specificity"]
            + prompt_analysis.context_score * weights["context"]
            + test_score * weights["test_inclusion"]
            + file_score * weights["file_refs"]
        )

        return round(score, 1)

    def _generate_recommendations(
        self,
        prompt_analysis: PromptQualityAnalysis,
        executor_rates: list[ExecutorSuccessRate],
        error_patterns: list[ErrorPattern],
        iteration_data: dict,
    ) -> list[AnalysisRecommendation]:
        """Generate recommendations based on analysis."""
        recommendations = []
        rec_id = 0

        # Prompt quality recommendations
        if prompt_analysis.total_prompts_analyzed > 0:
            total = prompt_analysis.total_prompts_analyzed
            test_ratio = prompt_analysis.prompts_with_test_req / total

            if test_ratio < 0.3:
                rec_id += 1
                recommendations.append(
                    AnalysisRecommendation(
                        id=f"rec_{rec_id:03d}",
                        priority="high",
                        category="prompt_quality",
                        title="プロンプトにテスト要件を追加",
                        description="プロンプトにテスト要件を含めると、平均イテレーション数を削減できます。",
                        impact="-2.3 iterations (推定)",
                        evidence={
                            "current_test_inclusion_rate": f"{test_ratio * 100:.1f}%",
                            "recommended_rate": "30%+",
                        },
                    )
                )

            if prompt_analysis.avg_word_count < 20:
                rec_id += 1
                recommendations.append(
                    AnalysisRecommendation(
                        id=f"rec_{rec_id:03d}",
                        priority="high",
                        category="prompt_quality",
                        title="プロンプトにより詳細なコンテキストを追加",
                        description=f"現在の平均語数は{prompt_analysis.avg_word_count:.1f}語です。"
                        "30-100語程度の詳細な説明を追加すると成功率が向上します。",
                        impact="+15% success rate (推定)",
                        evidence={
                            "current_avg_words": f"{prompt_analysis.avg_word_count:.1f}",
                            "optimal_range": "30-100 words",
                        },
                    )
                )

        # Executor recommendations
        if len(executor_rates) >= 2:
            sorted_rates = sorted(executor_rates, key=lambda x: x.success_rate, reverse=True)
            best = sorted_rates[0]
            worst = sorted_rates[-1]

            if best.success_rate - worst.success_rate > 10:
                rec_id += 1
                recommendations.append(
                    AnalysisRecommendation(
                        id=f"rec_{rec_id:03d}",
                        priority="medium",
                        category="executor_selection",
                        title=f"{best.executor_type.value}の使用を検討",
                        description=f"{best.executor_type.value}は{best.success_rate:.1f}%の成功率で、"
                        f"{worst.executor_type.value}({worst.success_rate:.1f}%)より高いパフォーマンスを示しています。",
                        impact=f"+{best.success_rate - worst.success_rate:.1f}% success rate",
                        evidence={
                            "best_executor": best.executor_type.value,
                            "best_rate": f"{best.success_rate:.1f}%",
                            "worst_executor": worst.executor_type.value,
                            "worst_rate": f"{worst.success_rate:.1f}%",
                        },
                    )
                )

        # Error pattern recommendations
        for pattern in error_patterns[:3]:
            if pattern.count >= 3 and pattern.failure_rate > 20:
                rec_id += 1
                pattern_names = {
                    "database_migration": "データベースマイグレーション",
                    "authentication": "認証関連",
                    "api_changes": "API変更",
                    "testing": "テスト関連",
                    "refactoring": "リファクタリング",
                    "other": "その他",
                }
                pattern_name = pattern_names.get(pattern.pattern, pattern.pattern)

                recommendations.append(
                    AnalysisRecommendation(
                        id=f"rec_{rec_id:03d}",
                        priority="medium" if pattern.failure_rate < 40 else "high",
                        category="error_pattern",
                        title=f"{pattern_name}タスクを小さく分割",
                        description=f"{pattern_name}タスクの失敗率が{pattern.failure_rate:.1f}%です。"
                        "タスクをより小さなステップに分割することで成功率を向上できます。",
                        impact=f"-{pattern.failure_rate * 0.5:.1f}% failure rate (推定)",
                        evidence={
                            "pattern": pattern.pattern,
                            "failure_count": pattern.count,
                            "failure_rate": f"{pattern.failure_rate:.1f}%",
                            "affected_files": pattern.affected_files[:5],
                        },
                    )
                )

        # Iteration efficiency recommendation
        avg_iterations = iteration_data["avg_iterations"]
        if avg_iterations > 5:
            rec_id += 1
            recommendations.append(
                AnalysisRecommendation(
                    id=f"rec_{rec_id:03d}",
                    priority="medium",
                    category="efficiency",
                    title="初期プロンプトの改善でイテレーションを削減",
                    description=f"平均イテレーション数が{avg_iterations:.1f}回と高めです。"
                    "初期プロンプトに詳細な要件と制約を含めることで、往復を減らせます。",
                    impact=f"-{(avg_iterations - 3) * 0.5:.1f} iterations (推定)",
                    evidence={
                        "current_avg_iterations": f"{avg_iterations:.1f}",
                        "target_iterations": "3-4",
                    },
                )
            )

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda x: priority_order.get(x.priority, 3))

        return recommendations[:6]  # Return top 6 recommendations
