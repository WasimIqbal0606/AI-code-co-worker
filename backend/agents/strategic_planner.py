"""
StrategicPlannerAgent — Enterprise-grade risk prioritization and rollout strategy.
Transforms raw finding lists into:
- Clustered related issues (SQL injection cluster, auth cluster, etc.)
- Priority-ranked remediation roadmap
- Effort estimates per cluster
- Phased rollout strategy with prerequisites and rollback plans
- Quick wins vs deferred items

This is what elevates the system from "issue dumping" to "strategic planning."
"""

from __future__ import annotations

import logging
from backend.agents.base_agent import BaseAgent
from backend.core.llm import TaskType
from backend.schemas import (
    EventType,
    Finding,
    RemediationRoadmap,
    RolloutPhase,
    Severity,
    StrategicCluster,
)

logger = logging.getLogger(__name__)

STRATEGIC_PLANNER_SYSTEM_PROMPT = """You are a senior engineering manager and remediation strategist.
You receive a list of validated findings from a code analysis. Your job is to create an ACTIONABLE remediation roadmap.

You must do THREE things:

## 1. CLUSTER related findings
Group findings that share a root cause or should be fixed together.
Examples:
- All SQL injection findings → "SQL Injection Remediation" cluster
- All hardcoded secrets → "Secret Management Overhaul" cluster
- All missing auth checks → "Authentication Hardening" cluster
- All MD5/weak crypto → "Cryptography Upgrade" cluster

For each cluster:
- cluster_id: unique identifier (e.g. "cluster_sql_injection")
- cluster_name: human-readable name
- category: "security", "performance", "architecture", "testing", "prompt_quality"
- finding_ids: list of finding IDs in this cluster
- root_cause: shared root cause explanation
- combined_severity: highest severity in the cluster
- effort_estimate: realistic time estimate (e.g. "2-4 hours", "1-2 days")
- risk_score: 0-100 priority score where 100 = fix immediately

## 2. CREATE phased rollout strategy
Organize clusters into deployment phases:
- Phase 1: Critical security fixes (authentication, injection, secrets) — deploy ASAP
- Phase 2: High-priority fixes (crypto, rate limiting, XSS) — deploy within 1 week
- Phase 3: Medium improvements (architecture, performance) — deploy within 1 month
- Phase 4: Low-priority enhancements (tests, prompts, style) — backlog

For each phase:
- phase_number: 1, 2, 3, etc.
- phase_name: descriptive name
- description: what this phase accomplishes
- cluster_ids: which clusters are in this phase
- estimated_effort: total effort for this phase
- risk_level: "low", "medium", "high" — risk of introducing regressions
- prerequisites: which phase numbers must complete first
- rollback_strategy: how to roll back if something breaks

## 3. IDENTIFY quick wins and deferred items
- quick_wins: finding IDs that can be fixed in < 30 minutes with zero risk
- deferred: finding IDs that should be deferred (low impact, high effort, or needs more analysis)

Return ONLY valid JSON:
{
  "clusters": [
    {
      "cluster_id": "cluster_sql_injection",
      "cluster_name": "SQL Injection Remediation",
      "category": "security",
      "finding_ids": ["security_abc123", "security_def456"],
      "root_cause": "Raw string interpolation used in SQL queries throughout the application",
      "combined_severity": "critical",
      "effort_estimate": "2-4 hours",
      "risk_score": 95
    }
  ],
  "rollout_phases": [
    {
      "phase_number": 1,
      "phase_name": "Critical Security Fixes",
      "description": "Address all critical and high SQL injection, authentication, and secret management issues",
      "cluster_ids": ["cluster_sql_injection", "cluster_secrets"],
      "estimated_effort": "1 day",
      "risk_level": "low",
      "prerequisites": [],
      "rollback_strategy": "Revert to previous commit. These are isolated security fixes with no feature changes."
    }
  ],
  "executive_summary": "The codebase has 3 critical security clusters requiring immediate attention. Estimated total remediation: 3-5 days. Phase 1 (critical security) should be deployed within 24 hours.",
  "estimated_total_effort": "3-5 days",
  "quick_wins": ["security_abc123"],
  "deferred": ["architecture_xyz789"]
}

RULES:
- Clusters must contain at least 1 finding
- Risk score: 90-100 = critical/immediate, 70-89 = high, 40-69 = medium, 0-39 = low
- Quick wins = simple fixes with high confidence and no breaking changes
- Deferred = low severity, high effort, or info-level findings
- Be realistic about effort estimates
- Each phase should be independently deployable"""


class StrategicPlannerAgent(BaseAgent):
    """
    Enterprise-grade remediation strategist.
    Clusters, prioritizes, and creates phased rollout plans.
    """

    AGENT_NAME = "strategic_planner"

    async def analyze(self, files: dict[str, str], manifest_summary: str) -> list[Finding]:
        """Not used directly — StrategicPlannerAgent uses plan() instead."""
        return []

    async def plan(
        self,
        findings: list[Finding],
    ) -> RemediationRoadmap:
        """
        Create a strategic remediation roadmap from validated findings.

        Returns:
            RemediationRoadmap with clusters, phases, and priorities
        """
        if not findings:
            return RemediationRoadmap(
                executive_summary="No findings to plan remediation for.",
            )

        await self.emit(
            EventType.AGENT_STARTED,
            f"📊 Strategic planner analyzing {len(findings)} findings for prioritization...",
        )

        # Build the prompt
        findings_text = self._serialize_findings_for_planning(findings)

        # Pre-compute some statistics for the planner
        severity_counts = {}
        agent_counts = {}
        for f in findings:
            severity_counts[f.severity.value] = severity_counts.get(f.severity.value, 0) + 1
            agent_counts[f.agent] = agent_counts.get(f.agent, 0) + 1

        stats = (
            f"Severity breakdown: {severity_counts}\n"
            f"Agent breakdown: {agent_counts}\n"
            f"Total findings: {len(findings)}\n"
            f"Findings with auto-fixes: {sum(1 for f in findings if f.auto_fix)}\n"
            f"Findings with patches: {sum(1 for f in findings if f.patch)}"
        )

        user_prompt = (
            f"## Findings to strategize ({len(findings)} total):\n\n"
            f"{findings_text}\n\n"
            f"## Statistics:\n{stats}\n\n"
            f"Create a prioritized remediation roadmap with clusters, "
            f"rollout phases, quick wins, and deferred items."
        )

        await self.emit(
            EventType.AGENT_PROGRESS,
            "🧠 Computing risk clusters and rollout strategy via Mistral...",
            progress=0.3,
        )

        try:
            result = await self.llm.generate_json(
                STRATEGIC_PLANNER_SYSTEM_PROMPT, user_prompt,
                task_type=TaskType.STRATEGIC_PLANNING,
            )

            await self.emit(
                EventType.AGENT_PROGRESS,
                "📋 Building remediation roadmap...",
                progress=0.8,
            )

            roadmap = self._build_roadmap(findings, result)

            # Assign cluster IDs back to findings
            for cluster in roadmap.clusters:
                for fid in cluster.finding_ids:
                    for f in findings:
                        if f.id == fid:
                            f.cluster_id = cluster.cluster_id

            await self.emit(
                EventType.AGENT_PROGRESS,
                f"📊 Roadmap: {roadmap.total_clusters} clusters, "
                f"{len(roadmap.rollout_phases)} phases, "
                f"{len(roadmap.quick_wins)} quick wins",
                progress=0.9,
            )

        except Exception as e:
            logger.error(f"StrategicPlannerAgent failed: {e}")
            await self.emit(
                EventType.AGENT_PROGRESS,
                f"❌ Strategic planning error: {e}. Generating fallback roadmap.",
                progress=1.0,
            )
            roadmap = self._fallback_roadmap(findings)

        await self.emit(
            EventType.AGENT_DONE,
            f"✅ Strategic plan complete — {roadmap.total_clusters} clusters, "
            f"{len(roadmap.rollout_phases)} deployment phases",
            progress=1.0,
        )

        return roadmap

    def _serialize_findings_for_planning(self, findings: list[Finding]) -> str:
        """Convert findings to text optimized for strategic planning."""
        parts = []
        for i, f in enumerate(findings, 1):
            auto_fix_info = ""
            if f.auto_fix:
                auto_fix_info = (
                    f"\n  Has Auto-Fix: YES ({f.auto_fix.fix_type})"
                    f"\n  Auto-Fix Confidence: {f.auto_fix.confidence}"
                    f"\n  Safe to Auto-Apply: {f.auto_fix.is_safe_to_auto_apply}"
                )

            parts.append(
                f"### Finding {i} (ID: {f.id})\n"
                f"  Agent: {f.agent}\n"
                f"  Title: {f.title}\n"
                f"  Severity: {f.severity.value}\n"
                f"  Confidence: {f.confidence}\n"
                f"  File: {f.file_path}\n"
                f"  Description: {f.description[:200]}\n"
                f"  Recommendation: {f.recommendation[:200]}"
                f"{auto_fix_info}\n"
            )
        return "\n".join(parts)

    def _build_roadmap(self, findings: list[Finding], result: dict) -> RemediationRoadmap:
        """Build RemediationRoadmap from LLM response."""
        # Parse clusters
        clusters = []
        for c in result.get("clusters", []):
            clusters.append(StrategicCluster(
                cluster_id=c.get("cluster_id", ""),
                cluster_name=c.get("cluster_name", ""),
                category=c.get("category", ""),
                finding_ids=c.get("finding_ids", []),
                root_cause=c.get("root_cause", ""),
                combined_severity=c.get("combined_severity", "medium"),
                effort_estimate=c.get("effort_estimate", ""),
                risk_score=max(0, min(100, int(c.get("risk_score", 50)))),
            ))

        # Sort clusters by risk score (highest first)
        clusters.sort(key=lambda c: c.risk_score, reverse=True)

        # Parse rollout phases
        phases = []
        for p in result.get("rollout_phases", []):
            phases.append(RolloutPhase(
                phase_number=p.get("phase_number", 0),
                phase_name=p.get("phase_name", ""),
                description=p.get("description", ""),
                cluster_ids=p.get("cluster_ids", []),
                estimated_effort=p.get("estimated_effort", ""),
                risk_level=p.get("risk_level", "medium"),
                prerequisites=p.get("prerequisites", []),
                rollback_strategy=p.get("rollback_strategy", ""),
            ))

        # Sort phases by phase number
        phases.sort(key=lambda p: p.phase_number)

        return RemediationRoadmap(
            total_findings=len(findings),
            total_clusters=len(clusters),
            clusters=clusters,
            rollout_phases=phases,
            executive_summary=result.get("executive_summary", ""),
            estimated_total_effort=result.get("estimated_total_effort", ""),
            quick_wins=result.get("quick_wins", []),
            deferred=result.get("deferred", []),
        )

    def _fallback_roadmap(self, findings: list[Finding]) -> RemediationRoadmap:
        """Generate a basic roadmap without LLM when the planner fails."""
        # Group by severity
        critical = [f for f in findings if f.severity == Severity.CRITICAL]
        high = [f for f in findings if f.severity == Severity.HIGH]
        medium = [f for f in findings if f.severity == Severity.MEDIUM]
        low_info = [f for f in findings if f.severity in (Severity.LOW, Severity.INFO)]

        clusters = []
        phases = []

        if critical:
            cid = "cluster_critical"
            clusters.append(StrategicCluster(
                cluster_id=cid,
                cluster_name="Critical Issues",
                category="security",
                finding_ids=[f.id for f in critical],
                root_cause="Multiple critical-severity issues detected",
                combined_severity="critical",
                effort_estimate=f"{len(critical) * 2}-{len(critical) * 4} hours",
                risk_score=95,
            ))
            phases.append(RolloutPhase(
                phase_number=1,
                phase_name="Critical Fixes",
                description="Address all critical-severity findings immediately",
                cluster_ids=[cid],
                estimated_effort=f"{len(critical) * 2} hours",
                risk_level="low",
                rollback_strategy="Revert to previous commit",
            ))

        if high:
            cid = "cluster_high"
            clusters.append(StrategicCluster(
                cluster_id=cid,
                cluster_name="High Priority Issues",
                category="security",
                finding_ids=[f.id for f in high],
                root_cause="Multiple high-severity issues detected",
                combined_severity="high",
                effort_estimate=f"{len(high)}-{len(high) * 2} hours",
                risk_score=75,
            ))
            phases.append(RolloutPhase(
                phase_number=2,
                phase_name="High Priority Fixes",
                description="Address high-severity findings within 1 week",
                cluster_ids=[cid],
                estimated_effort=f"{len(high)} hours",
                risk_level="medium",
                rollback_strategy="Feature branch with staged rollout",
            ))

        quick_wins = [
            f.id for f in findings
            if f.auto_fix and f.auto_fix.is_safe_to_auto_apply
        ]
        deferred = [f.id for f in low_info]

        return RemediationRoadmap(
            total_findings=len(findings),
            total_clusters=len(clusters),
            clusters=clusters,
            rollout_phases=phases,
            executive_summary=(
                f"Fallback roadmap: {len(critical)} critical, {len(high)} high, "
                f"{len(medium)} medium, {len(low_info)} low/info findings."
            ),
            estimated_total_effort=f"{len(findings)}-{len(findings) * 2} hours",
            quick_wins=quick_wins,
            deferred=deferred,
        )
