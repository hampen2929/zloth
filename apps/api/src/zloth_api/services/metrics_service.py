"""Service for calculating and aggregating development metrics."""

from datetime import datetime, timedelta

from zloth_api.domain.enums import ExecutorType
from zloth_api.domain.models import (
    AgenticMetrics,
    CIMetrics,
    ConversationMetrics,
    ExecutorDistribution,
    MetricsDataPoint,
    MetricsDetail,
    MetricsSummary,
    MetricsTrend,
    PRMetrics,
    ProductivityMetrics,
    RealtimeMetrics,
    ReviewMetrics,
    RunMetrics,
)
from zloth_api.storage.dao import MetricsDAO


def _parse_period(period: str) -> tuple[datetime, datetime]:
    """Parse period string into start and end datetimes.

    Args:
        period: Period string like "1d", "7d", "30d", "90d", "all"

    Returns:
        Tuple of (period_start, period_end)
    """
    now = datetime.utcnow()
    period_end = now

    if period == "all":
        # Start from a very early date
        period_start = datetime(2020, 1, 1)
    elif period.endswith("d"):
        days = int(period[:-1])
        period_start = now - timedelta(days=days)
    elif period.endswith("w"):
        weeks = int(period[:-1])
        period_start = now - timedelta(weeks=weeks)
    elif period.endswith("h"):
        hours = int(period[:-1])
        period_start = now - timedelta(hours=hours)
    else:
        # Default to 30 days
        period_start = now - timedelta(days=30)

    return period_start, period_end


class MetricsService:
    """Service for calculating development metrics."""

    def __init__(self, metrics_dao: MetricsDAO):
        self.metrics_dao = metrics_dao

    async def get_metrics_detail(
        self,
        period: str = "30d",
        repo_id: str | None = None,
    ) -> MetricsDetail:
        """Get complete metrics detail for a period.

        Args:
            period: Period string (e.g., "7d", "30d", "90d", "all")
            repo_id: Optional repository filter

        Returns:
            Complete metrics detail
        """
        period_start, period_end = _parse_period(period)

        # Gather all metrics in parallel conceptually
        pr_data = await self.metrics_dao.get_pr_metrics(period_start, period_end, repo_id)
        message_data = await self.metrics_dao.get_message_metrics(period_start, period_end, repo_id)
        run_data = await self.metrics_dao.get_run_metrics(period_start, period_end, repo_id)
        executor_data = await self.metrics_dao.get_executor_distribution(
            period_start, period_end, repo_id
        )
        ci_data = await self.metrics_dao.get_ci_metrics(period_start, period_end, repo_id)
        review_data = await self.metrics_dao.get_review_metrics(period_start, period_end, repo_id)
        agentic_data = await self.metrics_dao.get_agentic_metrics(period_start, period_end, repo_id)
        task_count = await self.metrics_dao.get_task_count(period_start, period_end, repo_id)
        realtime_data = await self.metrics_dao.get_realtime_metrics(repo_id)

        # Calculate derived metrics
        pr_metrics = self._build_pr_metrics(pr_data)
        conversation_metrics = self._build_conversation_metrics(message_data, task_count)
        run_metrics = self._build_run_metrics(run_data)
        executor_distribution = self._build_executor_distribution(executor_data, run_data)
        ci_metrics = self._build_ci_metrics(ci_data, agentic_data)
        review_metrics = self._build_review_metrics(review_data)
        agentic_metrics = self._build_agentic_metrics(agentic_data)
        productivity_metrics = await self._build_productivity_metrics(
            period_start, period_end, repo_id, task_count, pr_data
        )
        realtime_metrics = RealtimeMetrics(**realtime_data)

        # Build summary
        summary = MetricsSummary(
            period=period,
            period_start=period_start,
            period_end=period_end,
            merge_rate=pr_metrics.merge_rate,
            avg_cycle_time_hours=productivity_metrics.avg_cycle_time_hours,
            throughput=productivity_metrics.throughput_per_week,
            run_success_rate=run_metrics.run_success_rate,
            total_tasks=task_count,
            total_prs=pr_metrics.total_prs,
            total_runs=run_metrics.total_runs,
            total_messages=conversation_metrics.total_messages,
        )

        # Calculate changes vs previous period
        summary = await self._add_period_comparisons(summary, period, repo_id)

        return MetricsDetail(
            summary=summary,
            pr_metrics=pr_metrics,
            conversation_metrics=conversation_metrics,
            run_metrics=run_metrics,
            executor_distribution=executor_distribution,
            ci_metrics=ci_metrics,
            review_metrics=review_metrics,
            agentic_metrics=agentic_metrics,
            productivity_metrics=productivity_metrics,
            realtime=realtime_metrics,
        )

    async def get_summary(
        self,
        period: str = "7d",
        repo_id: str | None = None,
    ) -> MetricsSummary:
        """Get a summary of key metrics.

        Args:
            period: Period string
            repo_id: Optional repository filter

        Returns:
            Metrics summary
        """
        detail = await self.get_metrics_detail(period, repo_id)
        return detail.summary

    async def get_realtime(self, repo_id: str | None = None) -> RealtimeMetrics:
        """Get current real-time metrics.

        Args:
            repo_id: Optional repository filter

        Returns:
            Real-time metrics
        """
        data = await self.metrics_dao.get_realtime_metrics(repo_id)
        return RealtimeMetrics(**data)

    async def get_trends(
        self,
        metric_names: list[str],
        period: str = "30d",
        granularity: str = "day",
        repo_id: str | None = None,
    ) -> list[MetricsTrend]:
        """Get trend data for specified metrics.

        Args:
            metric_names: List of metric names to include
            period: Period string
            granularity: "hour", "day", or "week"
            repo_id: Optional repository filter

        Returns:
            List of metric trends
        """
        period_start, period_end = _parse_period(period)
        trends = []

        for metric_name in metric_names:
            data_points = await self.metrics_dao.get_trend_data(
                metric_name, period_start, period_end, granularity, repo_id
            )

            # Convert to MetricsDataPoint
            points = []
            for dp in data_points:
                # Parse timestamp based on granularity
                ts_str = dp["timestamp"]
                if granularity == "hour":
                    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                elif granularity == "week":
                    # Week format is YYYY-WW, convert to first day of week
                    year, week = ts_str.split("-")
                    ts = datetime.strptime(f"{year}-W{week}-1", "%Y-W%W-%w")
                else:
                    ts = datetime.strptime(ts_str, "%Y-%m-%d")
                points.append(MetricsDataPoint(timestamp=ts, value=dp["value"]))

            # Calculate trend direction
            trend_direction = "stable"
            change_percentage = 0.0
            if len(points) >= 2:
                first_half = points[: len(points) // 2]
                second_half = points[len(points) // 2 :]
                if first_half and second_half:
                    first_avg = sum(p.value for p in first_half) / len(first_half)
                    second_avg = sum(p.value for p in second_half) / len(second_half)
                    if first_avg > 0:
                        change_percentage = ((second_avg - first_avg) / first_avg) * 100
                        if change_percentage > 5:
                            trend_direction = "up"
                        elif change_percentage < -5:
                            trend_direction = "down"

            trends.append(
                MetricsTrend(
                    metric_name=metric_name,
                    data_points=points,
                    trend=trend_direction,
                    change_percentage=change_percentage,
                )
            )

        return trends

    def _build_pr_metrics(self, data: dict) -> PRMetrics:
        """Build PR metrics from raw data."""
        total = data["total_prs"]
        merge_rate = (data["merged_prs"] / total * 100) if total > 0 else 0.0

        return PRMetrics(
            total_prs=data["total_prs"],
            merged_prs=data["merged_prs"],
            closed_prs=data["closed_prs"],
            open_prs=data["open_prs"],
            merge_rate=merge_rate,
            avg_time_to_merge_hours=data["avg_time_to_merge_hours"],
        )

    def _build_conversation_metrics(self, data: dict, task_count: int) -> ConversationMetrics:
        """Build conversation metrics from raw data."""
        avg_messages = data["total_messages"] / task_count if task_count > 0 else 0.0
        avg_user_messages = data["user_messages"] / task_count if task_count > 0 else 0.0

        return ConversationMetrics(
            total_messages=data["total_messages"],
            user_messages=data["user_messages"],
            assistant_messages=data["assistant_messages"],
            avg_messages_per_task=avg_messages,
            avg_user_messages_per_task=avg_user_messages,
        )

    def _build_run_metrics(self, data: dict) -> RunMetrics:
        """Build run metrics from raw data."""
        total = data["total_runs"]
        success_rate = (data["succeeded_runs"] / total * 100) if total > 0 else 0.0

        return RunMetrics(
            total_runs=data["total_runs"],
            succeeded_runs=data["succeeded_runs"],
            failed_runs=data["failed_runs"],
            canceled_runs=data["canceled_runs"],
            run_success_rate=success_rate,
            avg_run_duration_seconds=data["avg_run_duration_seconds"],
            avg_queue_wait_seconds=data["avg_queue_wait_seconds"],
        )

    def _build_executor_distribution(
        self, data: list[dict], run_data: dict
    ) -> list[ExecutorDistribution]:
        """Build executor distribution from raw data."""
        total = run_data["total_runs"]
        distribution = []

        for item in data:
            try:
                executor_type = ExecutorType(item["executor_type"])
                percentage = (item["count"] / total * 100) if total > 0 else 0.0
                distribution.append(
                    ExecutorDistribution(
                        executor_type=executor_type,
                        count=item["count"],
                        percentage=percentage,
                    )
                )
            except ValueError:
                # Skip unknown executor types
                pass

        return distribution

    def _build_ci_metrics(self, data: dict, agentic_data: dict) -> CIMetrics:
        """Build CI metrics from raw data."""
        total = data["total_ci_checks"]
        success_rate = (data["passed_ci_checks"] / total * 100) if total > 0 else 0.0

        return CIMetrics(
            total_ci_checks=data["total_ci_checks"],
            passed_ci_checks=data["passed_ci_checks"],
            failed_ci_checks=data["failed_ci_checks"],
            ci_success_rate=success_rate,
            avg_ci_fix_iterations=agentic_data["avg_ci_iterations"],
        )

    def _build_review_metrics(self, data: dict) -> ReviewMetrics:
        """Build review metrics from raw data."""
        return ReviewMetrics(
            total_reviews=data["total_reviews"],
            avg_review_score=data["avg_review_score"],
            critical_issues=data["critical_issues"],
            high_issues=data["high_issues"],
            medium_issues=data["medium_issues"],
            low_issues=data["low_issues"],
        )

    def _build_agentic_metrics(self, data: dict) -> AgenticMetrics:
        """Build agentic metrics from raw data."""
        total = data["total_agentic_runs"]
        completion_rate = (data["completed_agentic_runs"] / total * 100) if total > 0 else 0.0

        return AgenticMetrics(
            total_agentic_runs=data["total_agentic_runs"],
            completed_agentic_runs=data["completed_agentic_runs"],
            failed_agentic_runs=data["failed_agentic_runs"],
            agentic_completion_rate=completion_rate,
            avg_total_iterations=data["avg_total_iterations"],
            avg_ci_iterations=data["avg_ci_iterations"],
            avg_review_iterations=data["avg_review_iterations"],
        )

    async def _build_productivity_metrics(
        self,
        period_start: datetime,
        period_end: datetime,
        repo_id: str | None,
        task_count: int,
        pr_data: dict,
    ) -> ProductivityMetrics:
        """Build productivity metrics from raw data."""
        # Get cycle times
        cycle_times = await self.metrics_dao.get_cycle_times(period_start, period_end, repo_id)
        avg_cycle_time = sum(cycle_times) / len(cycle_times) if cycle_times else None

        # Calculate throughput per week
        period_days = (period_end - period_start).days
        weeks = period_days / 7 if period_days > 0 else 1
        throughput_per_week = pr_data["merged_prs"] / weeks if weeks > 0 else 0.0

        # Get first time success rate
        single_run_tasks = await self.metrics_dao.get_tasks_with_single_run_count(
            period_start, period_end, repo_id
        )
        first_time_success = (single_run_tasks / task_count * 100) if task_count > 0 else 0.0

        return ProductivityMetrics(
            avg_cycle_time_hours=avg_cycle_time,
            throughput_per_week=throughput_per_week,
            first_time_success_rate=first_time_success,
        )

    async def _add_period_comparisons(
        self,
        summary: MetricsSummary,
        period: str,
        repo_id: str | None,
    ) -> MetricsSummary:
        """Add comparison metrics vs previous period."""
        if period == "all":
            return summary

        # Calculate previous period
        period_start, period_end = _parse_period(period)
        period_length = period_end - period_start
        prev_start = period_start - period_length
        prev_end = period_start

        # Get previous period metrics
        prev_pr = await self.metrics_dao.get_pr_metrics(prev_start, prev_end, repo_id)

        # Calculate previous rates
        prev_merge_rate = (
            (prev_pr["merged_prs"] / prev_pr["total_prs"] * 100) if prev_pr["total_prs"] > 0 else 0
        )

        # Previous throughput
        period_days = (prev_end - prev_start).days
        weeks = period_days / 7 if period_days > 0 else 1
        prev_throughput = prev_pr["merged_prs"] / weeks if weeks > 0 else 0

        # Previous cycle time
        prev_cycle_times = await self.metrics_dao.get_cycle_times(prev_start, prev_end, repo_id)
        prev_avg_cycle = sum(prev_cycle_times) / len(prev_cycle_times) if prev_cycle_times else None

        # Calculate changes
        summary.merge_rate_change = summary.merge_rate - prev_merge_rate

        if prev_avg_cycle and summary.avg_cycle_time_hours:
            summary.cycle_time_change = summary.avg_cycle_time_hours - prev_avg_cycle

        summary.throughput_change = summary.throughput - prev_throughput

        return summary
