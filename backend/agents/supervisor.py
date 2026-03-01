"""
Supervisor — LangGraph orchestrator.
Reads repo files, constructs initial state, invokes the graph,
and streams events back to the store for SSE.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from backend.core.store import store
from backend.core.file_utils import read_file_content
from backend.graph.builder import compile_graph
from backend.schemas import (
    AgentEvent,
    EventType,
    Finding,
    PermissionLevel,
    RunMode,
    RunResult,
    RunStatus,
    SkillType,
)

logger = logging.getLogger(__name__)


async def _async_read_file(repo_path: str, rel_path: str) -> tuple[str, str]:
    """Read file content in a thread to avoid blocking the event loop."""
    content = await asyncio.to_thread(read_file_content, repo_path, rel_path)
    return rel_path, content


async def run_supervisor(
    run_id: str,
    repo_id: str,
    skills: list[SkillType],
    permission: PermissionLevel = PermissionLevel.PROPOSE_CHANGES,
    mode: RunMode = RunMode.MANUAL,
    user_request: str = "",
) -> None:
    """Main supervisor coroutine. Runs in the background via asyncio.create_task."""
    start = time.time()

    try:
        # Update run status
        run = await store.get_run(run_id)
        if not run:
            logger.error("Run %s not found in store — aborting", run_id)
            return
        run.status = RunStatus.RUNNING
        await store.update_run(run)

        # Load repo files
        manifest = await store.get_repo(repo_id)
        repo_path = await store.get_repo_path(repo_id)
        if not manifest or not repo_path:
            logger.error("Repo %s not found for run %s", repo_id, run_id)
            await _push_error(run_id, "Repo not found")
            run.status = RunStatus.FAILED
            await store.update_run(run)
            return

        # Read file contents asynchronously (non-blocking)
        read_tasks = [
            _async_read_file(repo_path, f.path)
            for f in manifest.files
        ]
        results = await asyncio.gather(*read_tasks, return_exceptions=True)

        files: dict[str, str] = {}
        for result in results:
            if isinstance(result, Exception):
                logger.warning("Failed to read file: %s", result)
                continue
            path, content = result
            if content:
                files[path] = content

        # Build manifest summary
        manifest_summary = "\n".join(
            f"  {f.path} ({f.language}, {f.size_bytes}B)"
            for f in manifest.files[:50]
        )

        # Construct initial graph state
        initial_state = {
            "run_id": run_id,
            "repo_id": repo_id,
            "user_request": user_request,
            "selected_skills": skills,
            "permission": permission,
            "mode": mode,
            "repo_manifest_summary": manifest_summary,
            "file_contents": files,
            "findings": [],
            "events": [],
            "summary": "",
            "total_files_analyzed": 0,
            "duration_seconds": 0.0,
            "skills_to_run": skills if mode == RunMode.MANUAL else [],
        }

        # Compile and invoke LangGraph
        graph = compile_graph()
        final_state = await graph.ainvoke(initial_state)

        # Finalize run
        duration = time.time() - start
        all_findings: list[Finding] = final_state.get("findings", [])

        run.findings = all_findings
        run.total_files_analyzed = final_state.get("total_files_analyzed", len(files))
        run.duration_seconds = round(duration, 2)
        run.status = RunStatus.COMPLETED
        run.summary = final_state.get("summary", f"Analyzed {len(files)} files, found {len(all_findings)} findings")
        run.skills_used = final_state.get("skills_to_run", skills)
        run.health_scores = final_state.get("health_scores", None)
        run.critic_summary = final_state.get("critique_summary", "")
        run.dependency_summary = final_state.get("dependency_summary", "")
        run.remediation_summary = final_state.get("remediation_summary", "")
        run.roadmap = final_state.get("roadmap", None)
        await store.update_run(run)

        logger.info(
            "Run %s completed: %d findings, %.1fs, health=%s",
            run_id, len(all_findings), duration,
            run.health_scores.overall if run.health_scores else "N/A",
        )

    except Exception as e:
        logger.exception("Supervisor error for run %s", run_id)
        run = await store.get_run(run_id)
        if run:
            run.status = RunStatus.FAILED
            await store.update_run(run)
        await _push_error(run_id, f"Supervisor error: {e}")


async def _push_error(run_id: str, msg: str) -> None:
    """Push an error event to the SSE stream."""
    event = AgentEvent(
        run_id=run_id,
        event_type=EventType.ERROR,
        agent="supervisor",
        message=msg,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    await store.push_event(event)
