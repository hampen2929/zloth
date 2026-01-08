    async def create_runs(self, task_id: str, data: RunCreate) -> list[Run]:
        """Create runs for multiple models or Claude Code.

        Args:
            task_id: Task ID.
            data: Run creation data with model IDs or executor type.

        Returns:
            List of created Run objects.
        """
        # Verify task exists
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        # Get repo for workspace
        repo = await self.repo_service.get(task.repo_id)
        if not repo:
            raise ValueError(f"Repo not found: {task.repo_id}")

        runs = []
        executors: list[ExecutorConfig] = []

        if data.executors:
            executors = data.executors
        else:
            # Backward compatibility logic
            existing_runs = await self.run_dao.list(task_id)
            
            # Use provided executor_type or default to PATCH_AGENT
            executor_type = data.executor_type or ExecutorType.PATCH_AGENT
            
            # Apply locking logic only for legacy single-executor mode
            if existing_runs:
                # DAO returns newest-first; the earliest run is last.
                locked_executor = existing_runs[-1].executor_type
                # If we are in legacy mode (no explicit executors list), respect the lock
                if data.executor_type and data.executor_type != locked_executor:
                     # Force the locked executor type
                     executor_type = locked_executor

            if executor_type == ExecutorType.PATCH_AGENT:
                model_ids = data.model_ids
                if not model_ids:
                    # Reuse models from history
                    patch_runs = [
                        r for r in existing_runs if r.executor_type == ExecutorType.PATCH_AGENT
                    ]
                    if patch_runs:
                        latest_instruction = patch_runs[0].instruction  # newest-first
                        model_ids = []
                        seen: set[str] = set()
                        for r in patch_runs:
                            if r.instruction != latest_instruction:
                                continue
                            if r.model_id and r.model_id not in seen:
                                seen.add(r.model_id)
                                model_ids.append(r.model_id)
                
                if not model_ids:
                    raise ValueError("model_ids required for patch_agent executor")
                
                for mid in model_ids:
                    executors.append(ExecutorConfig(executor_type=ExecutorType.PATCH_AGENT, model_id=mid))
            else:
                executors.append(ExecutorConfig(executor_type=executor_type))

        # Execute all configured runs
        for config in executors:
            if config.executor_type in (
                ExecutorType.CLAUDE_CODE,
                ExecutorType.CODEX_CLI,
                ExecutorType.GEMINI_CLI,
            ):
                run = await self._create_cli_run(
                    task_id=task_id,
                    repo=repo,
                    instruction=data.instruction,
                    base_ref=data.base_ref or repo.default_branch,
                    executor_type=config.executor_type,
                    message_id=data.message_id,
                )
                runs.append(run)
            elif config.executor_type == ExecutorType.PATCH_AGENT:
                if not config.model_id:
                    continue

                model = await self.model_service.get(config.model_id)
                if not model:
                    raise ValueError(f"Model not found: {config.model_id}")

                run = await self.run_dao.create(
                    task_id=task_id,
                    instruction=data.instruction,
                    executor_type=ExecutorType.PATCH_AGENT,
                    message_id=data.message_id,
                    model_id=config.model_id,
                    model_name=model.model_name,
                    provider=model.provider,
                    base_ref=data.base_ref or repo.default_branch,
                )
                runs.append(run)

                def make_patch_agent_coro(
                    r: Run, rp: Any
                ) -> Callable[[], Coroutine[Any, Any, None]]:
                    return lambda: self._execute_patch_agent_run(r, rp)

                self.queue.enqueue(
                    run.id,
                    make_patch_agent_coro(run, repo),
                )

        return runs
