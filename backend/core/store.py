"""
In-memory store for repos, runs, and events.
Persists repo manifests and completed runs to disk so they survive server restarts.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Optional

from backend.schemas import (
    AgentEvent,
    RepoManifest,
    RunResult,
    RunStatus,
)

log = logging.getLogger(__name__)

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
MANIFEST_FILENAME = "_manifest.json"


class Store:
    """Thread-safe in-memory store. Replace with DB adapter later."""

    def __init__(self):
        self._repos: dict[str, RepoManifest] = {}
        self._repo_paths: dict[str, str] = {}          # repo_id -> disk path
        self._runs: dict[str, RunResult] = {}
        self._events: dict[str, list[AgentEvent]] = {} # run_id -> ordered events
        self._event_signals: dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    # -- Internal helpers -------------------------------------------

    @property
    def _runs_dir(self) -> str:
        path = os.path.join(UPLOAD_DIR, "_runs")
        os.makedirs(path, exist_ok=True)
        return path

    def _run_path(self, run_id: str) -> str:
        return os.path.join(self._runs_dir, f"{run_id}.json")

    def _write_run_sync(self, run: RunResult, events: list[AgentEvent]) -> None:
        """Persist a run + its events to a JSON file on disk (sync I/O)."""
        try:
            data = {
                "run": run.model_dump(),
                "events": [e.model_dump() for e in events],
            }
            path = self._run_path(run.run_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as exc:
            log.warning("Could not persist run %s: %s", run.run_id, exc)

    async def _write_run(self, run: RunResult, events: list[AgentEvent]) -> None:
        """Non-blocking wrapper for disk persistence."""
        await asyncio.to_thread(self._write_run_sync, run, events)

    # -- Repos ------------------------------------------------------

    async def save_repo(self, manifest: RepoManifest, disk_path: str) -> None:
        async with self._lock:
            self._repos[manifest.repo_id] = manifest
            self._repo_paths[manifest.repo_id] = disk_path
        # Persist sidecar so we can restore after a restart
        sidecar = os.path.join(disk_path, MANIFEST_FILENAME)
        try:
            with open(sidecar, "w", encoding="utf-8") as f:
                json.dump(
                    {"manifest": manifest.model_dump(), "disk_path": disk_path},
                    f,
                    indent=2,
                )
        except Exception as exc:
            log.warning("Could not write repo sidecar %s: %s", sidecar, exc)

    async def get_repo(self, repo_id: str) -> Optional[RepoManifest]:
        return self._repos.get(repo_id)

    async def get_repo_path(self, repo_id: str) -> Optional[str]:
        return self._repo_paths.get(repo_id)

    def restore_from_disk(self) -> None:
        """Scan UPLOAD_DIR for repo sidecars and the _runs directory,
        reloading repos and completed runs into memory.
        Called once at startup - runs synchronously before the event loop starts.
        """
        if not os.path.isdir(UPLOAD_DIR):
            return

        repos_loaded = 0
        runs_loaded = 0

        # -- Restore repos --
        for entry in os.scandir(UPLOAD_DIR):
            if not entry.is_dir() or entry.name == "_runs":
                continue
            # Sidecar may be directly inside the upload folder...
            candidate = os.path.join(entry.path, MANIFEST_FILENAME)
            # ...or one level deeper (when zip had a single top-level folder)
            if not os.path.isfile(candidate):
                try:
                    sub = next(
                        e.path for e in os.scandir(entry.path) if e.is_dir()
                    )
                    candidate = os.path.join(sub, MANIFEST_FILENAME)
                except StopIteration:
                    continue
            if not os.path.isfile(candidate):
                continue
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    data = json.load(f)
                manifest = RepoManifest(**data["manifest"])
                disk_path = data["disk_path"]
                if not os.path.isdir(disk_path):
                    log.warning("Repo %s disk path missing, skipping.", manifest.repo_id)
                    continue
                self._repos[manifest.repo_id] = manifest
                self._repo_paths[manifest.repo_id] = disk_path
                repos_loaded += 1
            except Exception as exc:
                log.warning("Failed to restore repo from %s: %s", candidate, exc)

        # -- Restore runs --
        runs_dir = os.path.join(UPLOAD_DIR, "_runs")
        if os.path.isdir(runs_dir):
            for entry in os.scandir(runs_dir):
                if not entry.is_file() or not entry.name.endswith(".json"):
                    continue
                try:
                    with open(entry.path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    run = RunResult(**data["run"])
                    events = [AgentEvent(**e) for e in data.get("events", [])]

                    # If the run was interrupted mid-flight, mark it failed
                    if run.status in (RunStatus.PENDING, RunStatus.RUNNING):
                        run = run.model_copy(
                            update={
                                "status": RunStatus.FAILED,
                                "summary": "Run was interrupted by a server restart.",
                            }
                        )

                    self._runs[run.run_id] = run
                    self._events[run.run_id] = events
                    self._event_signals[run.run_id] = asyncio.Event()
                    self._event_signals[run.run_id].set()  # already finished
                    runs_loaded += 1
                except Exception as exc:
                    log.warning("Failed to restore run from %s: %s", entry.path, exc)

        if repos_loaded:
            log.info("Restored %d repo(s) from disk.", repos_loaded)
        if runs_loaded:
            log.info("Restored %d run(s) from disk.", runs_loaded)

    # -- Runs -------------------------------------------------------

    async def create_run(self, run: RunResult):
        async with self._lock:
            self._runs[run.run_id] = run
            self._events[run.run_id] = []
            self._event_signals[run.run_id] = asyncio.Event()
        # Persist immediately so run survives server restarts
        await self._write_run(run, [])

    async def get_run(self, run_id: str) -> Optional[RunResult]:
        return self._runs.get(run_id)

    async def update_run(self, run: RunResult):
        async with self._lock:
            self._runs[run.run_id] = run
            events = list(self._events.get(run.run_id, []))

        # Always persist to disk so runs survive server restarts
        await self._write_run(run, events)

    # -- Events -----------------------------------------------------

    async def push_event(self, event: AgentEvent):
        async with self._lock:
            if event.run_id in self._events:
                self._events[event.run_id].append(event)
                self._event_signals[event.run_id].set()

        # Persist run+events on terminal events so progress is saved
        if event.event_type.value in ("supervisor_done", "error"):
            run = self._runs.get(event.run_id)
            events = list(self._events.get(event.run_id, []))
            if run:
                await self._write_run(run, events)

    async def get_events(self, run_id: str, after: int = 0) -> list[AgentEvent]:
        events = self._events.get(run_id, [])
        return events[after:]

    async def wait_for_event(self, run_id: str, timeout: float = 30.0) -> bool:
        """Wait until a new event is pushed. Returns False on timeout."""
        signal = self._event_signals.get(run_id)
        if signal is None:
            return False
        try:
            await asyncio.wait_for(signal.wait(), timeout=timeout)
            signal.clear()
            return True
        except asyncio.TimeoutError:
            return False

    def is_run_done(self, run_id: str) -> bool:
        run = self._runs.get(run_id)
        if run is None:
            return True
        return run.status in (RunStatus.COMPLETED, RunStatus.FAILED)


# Global singleton
store = Store()
