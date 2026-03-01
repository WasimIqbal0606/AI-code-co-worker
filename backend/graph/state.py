"""
LangGraph orchestration layer for multi-agent AI Code Co-Worker.
Supervisor-driven graph with parallel skill execution,
remediation engine, and strategic planning.
"""

from __future__ import annotations

from typing import TypedDict, Annotated
from operator import add

from backend.schemas import (
    AgentEvent,
    Finding,
    HealthScores,
    RemediationRoadmap,
    SkillType,
    PermissionLevel,
    RunMode,
)


class GraphState(TypedDict, total=False):
    """LangGraph state that flows through all nodes."""
    # Inputs
    run_id: str
    repo_id: str
    user_request: str
    selected_skills: list[SkillType]
    permission: PermissionLevel
    mode: RunMode
    repo_manifest_summary: str
    file_contents: dict[str, str]           # path → content
    dependency_context: str                 # Injected by dependency_node

    # Accumulated outputs (use Annotated[list, add] for parallel merging)
    findings: Annotated[list[Finding], add]
    events: Annotated[list[AgentEvent], add]

    # Final
    summary: str
    critique_summary: str
    dependency_summary: str                 # Dependency scan summary for RunResult
    health_scores: HealthScores
    total_files_analyzed: int
    duration_seconds: float
    skills_to_run: list[SkillType]          # Resolved by router

    # Remediation & Strategic Planning (new)
    remediation_summary: str                # What auto-fixes were generated
    roadmap: RemediationRoadmap             # Prioritized rollout strategy

