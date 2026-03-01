"""
Shared Pydantic schemas for the AI Code Co-Worker system.
These define the contract between backend agents, API, and frontend.
Enhanced with permission gating, architecture plans, and benchmark guidance.
"""

from __future__ import annotations

import enum
from typing import Optional, Any

from pydantic import BaseModel, Field, field_validator


# ── Enums ────────────────────────────────────────────────────────────

class Severity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class SkillType(str, enum.Enum):
    SECURITY = "security"
    TESTS = "tests"
    SPEEDUP = "speedup"  # kept for API compat; internally = algorithmic_opt
    ARCHITECTURE = "architecture"
    PROMPT_QUALITY = "prompt_quality"


class EventType(str, enum.Enum):
    SUPERVISOR_STARTED = "supervisor_started"
    AGENT_STARTED = "agent_started"
    AGENT_PROGRESS = "agent_progress"
    AGENT_DONE = "agent_done"
    SUPERVISOR_DONE = "supervisor_done"
    ERROR = "error"


class RunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PermissionLevel(str, enum.Enum):
    READ_ONLY = "read_only"           # Analyze and report
    PROPOSE_CHANGES = "propose"       # Generate patches/tests but don't apply
    APPLY_AND_CHECK = "apply"         # Apply patch, run linters/tests (future)


class RunMode(str, enum.Enum):
    AUTO = "auto"                     # Supervisor chooses agents
    MANUAL = "manual"                 # User explicitly picks skills


# ── Core Models ──────────────────────────────────────────────────────

class Patch(BaseModel):
    """Unified diff patch for a single file."""
    file_path: str
    diff: str
    description: str = ""


class BenchmarkGuidance(BaseModel):
    """How to benchmark a performance improvement."""
    tool: str = ""                     # e.g. "pytest-benchmark", "time", "cProfile"
    command: str = ""                  # e.g. "python -m cProfile script.py"
    expected_improvement: str = ""     # e.g. "~10x for large inputs"
    before_complexity: str = ""        # e.g. "O(n²)"
    after_complexity: str = ""         # e.g. "O(n)"


class ArchitecturePlan(BaseModel):
    """Structured architecture migration plan."""
    current_summary: str = ""
    proposed_changes: str = ""
    risks_tradeoffs: str = ""
    refactor_steps: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    ascii_diagram: str = ""


class TestRunInstructions(BaseModel):
    """How to run generated tests."""
    framework: str = ""                # e.g. "pytest", "jest"
    install_command: str = ""          # e.g. "pip install pytest"
    run_command: str = ""              # e.g. "pytest tests/test_module_name.py -v"
    notes: str = ""


# ── Auto-Fix Remediation Models ──────────────────────────────────────

class AutoFixResult(BaseModel):
    """Production-ready auto-fix for a single finding."""
    finding_id: str = ""               # Links back to the original Finding
    file_path: str = ""                # File being modified
    original_code: str = ""            # The vulnerable/bad code block
    fixed_code: str = ""               # The rewritten, production-ready code
    fix_type: str = ""                 # e.g. "parameterized_query", "bcrypt_upgrade", "orm_migration"
    explanation: str = ""              # Why this fix is correct
    breaking_changes: list[str] = Field(default_factory=list)  # What might break
    imports_needed: list[str] = Field(default_factory=list)     # New imports required
    dependencies_needed: list[str] = Field(default_factory=list)  # pip install X
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    is_safe_to_auto_apply: bool = False  # True if fix is trivially safe


# ── Strategic Planning Models ────────────────────────────────────────

class StrategicCluster(BaseModel):
    """Group of related findings that should be fixed together."""
    cluster_id: str = ""
    cluster_name: str = ""             # e.g. "SQL Injection Remediation"
    category: str = ""                 # e.g. "security", "performance", "architecture"
    finding_ids: list[str] = Field(default_factory=list)
    root_cause: str = ""               # Shared root cause
    combined_severity: str = ""        # Highest severity in cluster
    effort_estimate: str = ""          # e.g. "2-4 hours", "1-2 days"
    risk_score: int = Field(default=0, ge=0, le=100)  # 0-100 priority


class RolloutPhase(BaseModel):
    """A phase in the remediation rollout strategy."""
    phase_number: int = 0
    phase_name: str = ""               # e.g. "Critical Security Fixes"
    description: str = ""
    cluster_ids: list[str] = Field(default_factory=list)
    estimated_effort: str = ""         # e.g. "1 day"
    risk_level: str = ""               # "low", "medium", "high"
    prerequisites: list[str] = Field(default_factory=list)  # Phases that must complete first
    rollback_strategy: str = ""

    @field_validator("prerequisites", mode="before")
    @classmethod
    def coerce_prerequisites(cls, v):
        """LLM sometimes returns ints instead of strings — coerce them."""
        if isinstance(v, list):
            return [str(item) for item in v]
        return v

    @field_validator("cluster_ids", mode="before")
    @classmethod
    def coerce_cluster_ids(cls, v):
        if isinstance(v, list):
            return [str(item) for item in v]
        return v


class RemediationRoadmap(BaseModel):
    """Strategic remediation plan with prioritized rollout."""
    total_findings: int = 0
    total_clusters: int = 0
    clusters: list[StrategicCluster] = Field(default_factory=list)
    rollout_phases: list[RolloutPhase] = Field(default_factory=list)
    executive_summary: str = ""        # 2-3 sentence summary for stakeholders
    estimated_total_effort: str = ""   # e.g. "3-5 days"
    quick_wins: list[str] = Field(default_factory=list)  # Finding IDs fixable in < 30min
    deferred: list[str] = Field(default_factory=list)     # Finding IDs to defer


class Finding(BaseModel):
    """Universal finding returned by every agent."""
    id: str = Field(default="", description="Unique finding ID")
    agent: str = Field(description="Which agent produced this finding")
    severity: Severity = Severity.INFO
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    title: str
    description: str
    file_path: str = ""
    line_range: Optional[list[int]] = None
    evidence: str = ""
    recommendation: str = ""
    patch: Optional[Patch] = None
    explain_steps: list[str] = Field(
        default_factory=list,
        description="Safe, non-sensitive reasoning trace bullets",
    )
    # Enhanced fields
    benchmark: Optional[BenchmarkGuidance] = None
    architecture_plan: Optional[ArchitecturePlan] = None
    test_instructions: Optional[TestRunInstructions] = None
    why_slow: str = ""                 # AlgorithmicOpt: why this is slow
    complexity_delta: str = ""         # AlgorithmicOpt: expected complexity change
    # Auto-Fix Remediation fields
    auto_fix: Optional[AutoFixResult] = None
    cluster_id: str = ""               # Strategic planner assigns this


class FileEntry(BaseModel):
    """A single file in the repo manifest."""
    path: str
    size_bytes: int
    language: str = ""


class RepoManifest(BaseModel):
    """Filtered file list for a repo workspace."""
    repo_id: str
    total_files: int
    total_size_bytes: int
    files: list[FileEntry]


class AgentEvent(BaseModel):
    """SSE event emitted during a run."""
    run_id: str
    event_type: EventType
    agent: str = ""
    message: str = ""
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    findings_count: int = 0
    timestamp: str = ""


class RunRequest(BaseModel):
    """Request to start a new analysis run."""
    repo_id: str
    skills: list[SkillType] = Field(default_factory=list)
    permission: PermissionLevel = PermissionLevel.PROPOSE_CHANGES
    mode: RunMode = RunMode.MANUAL
    user_request: str = ""             # Free-text for auto mode


class HealthScores(BaseModel):
    """Repository health scores (0–100 each)."""
    security: int = Field(default=100, ge=0, le=100)
    performance: int = Field(default=100, ge=0, le=100)
    architecture: int = Field(default=100, ge=0, le=100)
    tests: int = Field(default=100, ge=0, le=100)
    overall: int = Field(default=100, ge=0, le=100)


class RunResult(BaseModel):
    """Final aggregated result of a run."""
    run_id: str
    repo_id: str
    status: RunStatus = RunStatus.COMPLETED
    skills_used: list[SkillType] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    summary: str = ""
    total_files_analyzed: int = 0
    duration_seconds: float = 0.0
    permission: PermissionLevel = PermissionLevel.PROPOSE_CHANGES
    health_scores: Optional[HealthScores] = None
    critic_summary: str = ""                # Critic agent quality assessment
    dependency_summary: str = ""             # Dependency scan summary
    # Auto-Fix Remediation & Strategic Planning
    remediation_summary: str = ""            # What was auto-fixed
    roadmap: Optional[RemediationRoadmap] = None  # Prioritized rollout strategy
