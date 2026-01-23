"""Comparison service for judging outputs across multiple runs.

MVP: aggregates target runs, builds a compact prompt and calls judge LLM
via ModelService/LLMRouter to produce scores and a winner.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from zloth_api.domain.enums import ExecutorType, RunStatus
from zloth_api.domain.models import (
    Comparison,
    ComparisonCreate,
    ComparisonCreated,
    ComparisonScore,
)
from zloth_api.services.model_service import ModelService
from zloth_api.agents.llm_router import LLMConfig, LLMRouter
from zloth_api.storage.dao import ComparisonDAO, RunDAO, TaskDAO

logger = logging.getLogger(__name__)


JUDGE_SYSTEM = (
    "You are an expert software engineering judge. Compare multiple model outputs "
    "for a coding task. Return STRICT JSON only, no markdown."
)

JUDGE_USER_TEMPLATE = (
    "Task instruction:\n{instruction}\n\n"
    "We have N candidate implementations. For each candidate provide: "
    "score (0.0-1.0), pros[], cons[], and rationale. Then select overall_winner_run_id.\n"
    "Criteria: {criteria}.\n\n"
    "Candidates (JSON lines):\n{candidates}\n\n"
    "Respond with JSON:\n"
    "{\n  \"overall_winner_run_id\": string,\n  \"overall_summary\": string,\n  \"scores\": [{\n    \"run_id\": string, \"score\": number, \"pros\": [string], \"cons\": [string], \"rationale\": string\n  }]\n}"
)


class ComparisonService:
    """Service to run and retrieve comparisons."""

    def __init__(
        self,
        comparison_dao: ComparisonDAO,
        run_dao: RunDAO,
        task_dao: TaskDAO,
        model_service: ModelService,
        llm_router: LLMRouter | None = None,
    ) -> None:
        self.comparison_dao = comparison_dao
        self.run_dao = run_dao
        self.task_dao = task_dao
        self.model_service = model_service
        self.llm_router = llm_router or LLMRouter()

    async def create(self, task_id: str, data: ComparisonCreate) -> ComparisonCreated:
        # Validate task
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError("Task not found")

        # Resolve judge profile (optional)
        judge_model_name: str | None = None
        if data.judge_model_id:
            judge_profile = await self.model_service.get(data.judge_model_id)
            if not judge_profile:
                raise ValueError("Judge model not found")
            judge_model_name = judge_profile.display_name or judge_profile.model_name

        record = await self.comparison_dao.create(
            task_id=task_id,
            message_id=data.message_id,
            target_run_ids=data.target_run_ids,
            judge_model_id=data.judge_model_id,
            judge_model_name=judge_model_name,
        )

        # Fire-and-forget execution
        asyncio.create_task(self._execute(record.id, data))
        return ComparisonCreated(comparison_id=record.id)

    async def get(self, comparison_id: str) -> Comparison | None:
        return await self.comparison_dao.get(comparison_id)

    async def list_by_task(self, task_id: str) -> list[Comparison]:
        return await self.comparison_dao.list_by_task(task_id)

    async def _execute(self, comparison_id: str, data: ComparisonCreate) -> None:
        logs: list[str] = []
        try:
            await self.comparison_dao.update_status(
                comparison_id,
                RunStatus.RUNNING,
                started_at=datetime.utcnow().isoformat(),
            )
            logs.append("Comparison started")

            # Load runs
            runs = []
            for run_id in data.target_run_ids:
                run = await self.run_dao.get(run_id)
                if run:
                    runs.append(run)
            if len(runs) < 2:
                raise ValueError("At least two runs required")

            # Build candidate lines
            candidate_lines: list[str] = []
            for r in runs:
                # Keep payload compact (truncate patch if huge)
                patch = (r.patch or "")
                if len(patch) > 60000:
                    patch = patch[:60000] + "\n...<truncated>"
                candidate = {
                    "run_id": r.id,
                    "executor_type": r.executor_type.value,
                    "summary": r.summary or "",
                    "files_changed": [
                        {"path": f.path, "added": f.added_lines, "removed": f.removed_lines}
                        for f in (r.files_changed or [])
                    ],
                    "patch": patch,
                }
                candidate_lines.append(json.dumps(candidate))

            instruction = runs[0].instruction
            criteria = ", ".join(data.criteria or [])
            prompt_user = JUDGE_USER_TEMPLATE.format(
                instruction=instruction,
                criteria=criteria,
                candidates="\n".join(candidate_lines),
            )

            # Resolve judge LLM config
            if data.judge_model_id:
                profile = await self.model_service.get(data.judge_model_id)
                api_key = await self.model_service.get_decrypted_key(data.judge_model_id)
                if not profile or not api_key:
                    raise ValueError("Judge model credentials not found")
                config = LLMConfig(
                    provider=profile.provider,
                    model_name=profile.model_name,
                    api_key=api_key,
                    temperature=0.0,
                    max_tokens=2048,
                )
            else:
                # Fallback: pick first env model if none specified
                models = await self.model_service.list()
                if not models:
                    raise ValueError("No models configured for judge")
                profile = models[0]
                api_key = await self.model_service.get_decrypted_key(profile.id)
                if not api_key:
                    raise ValueError("Judge model key not found")
                config = LLMConfig(
                    provider=profile.provider,
                    model_name=profile.model_name,
                    api_key=api_key,
                    temperature=0.0,
                    max_tokens=2048,
                )

            client = self.llm_router.get_client(config)
            logs.append(f"Calling judge model: {config.provider.value}/{config.model_name}")
            raw = await client.generate(
                messages=[{"role": "user", "content": prompt_user}],
                system=JUDGE_SYSTEM,
            )

            # Parse JSON
            try:
                data_json = json.loads(raw)
            except Exception:
                # Try to recover from accidental markdown fences
                cleaned = raw.strip().strip("`")
                data_json = json.loads(cleaned)

            overall_winner = data_json.get("overall_winner_run_id")
            overall_summary = data_json.get("overall_summary")
            scores_data = data_json.get("scores", [])
            scores: list[ComparisonScore] = []
            for s in scores_data:
                run_id = s.get("run_id")
                run = next((r for r in runs if r.id == run_id), None)
                if not run:
                    continue
                score = float(s.get("score", 0))
                pros = s.get("pros", []) or []
                cons = s.get("cons", []) or []
                rationale = s.get("rationale")
                scores.append(
                    ComparisonScore(
                        run_id=run.id,
                        executor_type=run.executor_type,
                        score=score,
                        pros=pros,
                        cons=cons,
                        rationale=rationale,
                    )
                )

            await self.comparison_dao.update_status(
                comparison_id,
                RunStatus.SUCCEEDED,
                overall_winner_run_id=overall_winner,
                overall_summary=overall_summary,
                scores=scores,
                logs=logs,
                completed_at=datetime.utcnow().isoformat(),
            )
        except Exception as e:
            logger.exception("Comparison failed")
            logs.append(f"Comparison failed: {e}")
            await self.comparison_dao.update_status(
                comparison_id,
                RunStatus.FAILED,
                logs=logs,
                error=str(e),
                completed_at=datetime.utcnow().isoformat(),
            )

