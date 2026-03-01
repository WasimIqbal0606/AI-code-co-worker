"""
Run routes: start run, SSE stream events, get result, download patches.
Supports auto/manual mode and permission levels.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import uuid
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from backend.core.store import store
from backend.schemas import (
    AgentEvent,
    EventType,
    PermissionLevel,
    RunMode,
    RunRequest,
    RunResult,
    RunStatus,
)

router = APIRouter(prefix="/run", tags=["run"])


@router.post("", response_model=dict)
async def start_run(req: RunRequest):
    """Start a new analysis run. Returns run_id."""
    # Validate repo exists
    manifest = await store.get_repo(req.repo_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Repo not found")

    run_id = uuid.uuid4().hex[:12]
    run = RunResult(
        run_id=run_id,
        repo_id=req.repo_id,
        status=RunStatus.PENDING,
        skills_used=req.skills,
        permission=req.permission,
    )
    await store.create_run(run)

    # Start supervisor in background
    from backend.agents.supervisor import run_supervisor
    asyncio.create_task(
        run_supervisor(
            run_id=run_id,
            repo_id=req.repo_id,
            skills=req.skills,
            permission=req.permission,
            mode=req.mode,
            user_request=req.user_request,
        )
    )

    return {"run_id": run_id}


@router.get("/{run_id}/events")
async def stream_events(run_id: str):
    """SSE stream of AgentEvents for a run."""
    run = await store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator():
        cursor = 0

        # If the run is already done (restored from disk or already finished),
        # immediately flush all stored events and close the stream.
        if store.is_run_done(run_id):
            all_events = await store.get_events(run_id, after=0)
            for evt in all_events:
                yield {
                    "event": evt.event_type.value,
                    "data": evt.model_dump_json(),
                }

            # Ensure a supervisor_done event is sent so the frontend closes cleanly
            has_done_event = any(
                e.event_type.value in ("supervisor_done", "error")
                for e in all_events
            )
            if not has_done_event:
                from backend.schemas import AgentEvent, EventType
                done_evt = AgentEvent(
                    run_id=run_id,
                    event_type=EventType.SUPERVISOR_DONE,
                    agent="supervisor",
                    message=run.summary or "Run completed.",
                )
                yield {
                    "event": done_evt.event_type.value,
                    "data": done_evt.model_dump_json(),
                }
            return  # Close the stream

        # Run is still in progress — stream live events
        while True:
            events = await store.get_events(run_id, after=cursor)
            for evt in events:
                yield {
                    "event": evt.event_type.value,
                    "data": evt.model_dump_json(),
                }
                cursor += 1

            # Check if done
            if store.is_run_done(run_id):
                final_events = await store.get_events(run_id, after=cursor)
                for evt in final_events:
                    yield {
                        "event": evt.event_type.value,
                        "data": evt.model_dump_json(),
                    }
                break

            # Wait for new events
            await store.wait_for_event(run_id, timeout=10.0)

    return EventSourceResponse(event_generator())


@router.get("/{run_id}/result", response_model=RunResult)
async def get_result(run_id: str):
    """Return the final RunResult."""
    run = await store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/{run_id}/download")
async def download_patches(run_id: str):
    """Download a zip bundle with patches, generated tests, and run_result.json."""
    run = await store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status != RunStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Run not completed yet")

    # Permission check
    if run.permission == PermissionLevel.READ_ONLY:
        raise HTTPException(
            status_code=403,
            detail="Read-only mode: patches cannot be downloaded. Switch to 'Propose Changes' permission."
        )

    # Build zip in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add run_result.json (always included)
        zf.writestr("run_result.json", run.model_dump_json(indent=2))

        # Check if any auto-fixes were generated
        has_auto_fixes = any(
            f.auto_fix and f.auto_fix.fixed_code
            for f in run.findings
        )

        if has_auto_fixes:
            # ── AUTO-FIX MODE ────────────────────────────────────
            # Only include the production-ready fixed files + roadmap.
            # No patches or test files — the auto-fixes ARE the deliverable.

            for finding in run.findings:
                if not (finding.auto_fix and finding.auto_fix.fixed_code):
                    continue

                fix = finding.auto_fix
                safe_name = fix.file_path.replace("/", "_").replace("\\", "_")

                # Write the fixed source code file
                zf.writestr(
                    f"auto_fixes/{safe_name}",
                    fix.fixed_code,
                )

                # Write a metadata file with context
                fix_meta = (
                    f"# Auto-Fix: {fix.fix_type}\n"
                    f"# File: {fix.file_path}\n"
                    f"# Finding: {fix.finding_id}\n"
                    f"# Confidence: {fix.confidence}\n"
                    f"# Safe to auto-apply: {fix.is_safe_to_auto_apply}\n"
                    f"# Explanation: {fix.explanation}\n"
                )
                if fix.imports_needed:
                    fix_meta += f"# Imports needed: {', '.join(fix.imports_needed)}\n"
                if fix.dependencies_needed:
                    fix_meta += f"# Dependencies: {', '.join(fix.dependencies_needed)}\n"
                if fix.breaking_changes:
                    fix_meta += f"# Breaking changes: {'; '.join(fix.breaking_changes)}\n"
                fix_meta += f"\n# === ORIGINAL CODE ===\n{fix.original_code}\n"
                fix_meta += f"\n# === FIXED CODE ===\n{fix.fixed_code}\n"
                zf.writestr(
                    f"auto_fixes/{safe_name}.meta.txt",
                    fix_meta,
                )

            # Add remediation roadmap
            if run.roadmap:
                zf.writestr(
                    "remediation_roadmap.json",
                    run.roadmap.model_dump_json(indent=2),
                )

        else:
            # ── LEGACY MODE (no auto-fixes available) ────────────
            # Fall back to patches + generated tests.

            patch_idx = 0
            for finding in run.findings:
                if finding.patch:
                    patch_idx += 1
                    safe_name = finding.patch.file_path.replace("/", "_").replace("\\", "_")
                    zf.writestr(
                        f"patches/{patch_idx:03d}_{safe_name}.diff",
                        finding.patch.diff,
                    )

                if finding.test_instructions and finding.patch:
                    zf.writestr(
                        f"tests_generated/{finding.patch.file_path}",
                        finding.patch.diff,
                    )

            # Check for generated test files on disk
            repo_path = await store.get_repo_path(run.repo_id)
            if repo_path:
                tests_dir = os.path.join(repo_path, ".generated_tests")
                if os.path.isdir(tests_dir):
                    for root, _, files in os.walk(tests_dir):
                        for fname in files:
                            full = os.path.join(root, fname)
                            rel = os.path.relpath(full, tests_dir).replace("\\", "/")
                            with open(full, "r", encoding="utf-8", errors="replace") as fh:
                                zf.writestr(f"tests_generated/{rel}", fh.read())

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=coworker_run_{run_id}.zip"},
    )
