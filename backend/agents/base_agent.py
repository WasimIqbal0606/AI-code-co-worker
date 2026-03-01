"""
Base agent class — shared by all worker agents.
Provides SSE event emission, finding ID generation, and confidence normalization.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from backend.core.llm import LLMAdapter
from backend.core.store import store
from backend.schemas import AgentEvent, EventType, Finding

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base class for all worker agents."""

    AGENT_NAME: str = "base"

    def __init__(self, llm: LLMAdapter, run_id: str) -> None:
        self.llm = llm
        self.run_id = run_id

    async def emit(
        self,
        event_type: EventType,
        message: str = "",
        progress: float = 0.0,
        findings_count: int = 0,
    ) -> None:
        """Push an SSE event to the store for real-time streaming."""
        event = AgentEvent(
            run_id=self.run_id,
            event_type=event_type,
            agent=self.AGENT_NAME,
            message=message,
            progress=progress,
            findings_count=findings_count,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        await store.push_event(event)

    async def analyze(
        self, files: dict[str, str], manifest_summary: str
    ) -> list[Finding]:
        """
        Analyze the given files. Must be overridden by subclasses.

        Args:
            files: dict of relative_path → file_content
            manifest_summary: short summary of the repo structure

        Returns:
            List of Finding objects
        """
        logger.warning(
            "%s.analyze() not implemented — returning empty findings",
            self.__class__.__name__,
        )
        return []

    def _make_finding_id(self) -> str:
        """Generate a unique ID for a finding."""
        return f"{self.AGENT_NAME}_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _normalize_confidence(raw: object) -> float:
        """Normalize confidence from LLM output to 0.0–1.0 range.

        Handles: floats, ints, percentages (>1.0), strings, and edge cases.
        """
        try:
            val = float(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.7  # safe default

        # If LLM returned a percentage like 85 instead of 0.85
        if val > 1.0:
            val = val / 100.0

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, val))
