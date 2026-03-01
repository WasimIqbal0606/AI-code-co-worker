"""
LangGraph node functions for the multi-agent orchestration.
Each node reads from GraphState, does work, and returns partial state updates.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from backend.graph.state import GraphState
from backend.schemas import (
    AgentEvent,
    EventType,
    Finding,
    SkillType,
    RunMode,
)
from backend.core.llm import get_llm
from backend.core.store import store

logger = logging.getLogger(__name__)


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event(run_id: str, etype: EventType, agent: str = "supervisor", msg: str = "", progress: float = 0.0, fc: int = 0) -> AgentEvent:
    return AgentEvent(
        run_id=run_id, event_type=etype, agent=agent,
        message=msg, progress=progress, findings_count=fc, timestamp=_ts(),
    )


# ── Supervisor Node ──────────────────────────────────────────────────

async def supervisor_node(state: GraphState) -> dict:
    """Kickoff: emit supervisor_started, prepare context."""
    run_id = state["run_id"]
    skills = state.get("selected_skills", [])
    mode = state.get("mode", RunMode.MANUAL)
    user_req = state.get("user_request", "")

    msg = f"Starting analysis with {len(skills)} skills"
    if mode == RunMode.AUTO and user_req:
        msg = f"Auto-mode: interpreting '{user_req[:80]}'"

    evt = _event(run_id, EventType.SUPERVISOR_STARTED, msg=msg)
    await store.push_event(evt)

    return {
        "events": [evt],
        "findings": [],
    }


# ── Dependency Analyzer Node ─────────────────────────────────────────

async def dependency_node(state: GraphState) -> dict:
    """Parse dependency manifests and produce findings before routing."""
    from backend.agents.dependency_analyzer import DependencyAnalyzer

    run_id = state["run_id"]
    file_contents = state.get("file_contents", {})

    evt = _event(run_id, EventType.AGENT_STARTED, agent="dependency",
                  msg=f"📦 Scanning dependencies across {len(file_contents)} files...")
    await store.push_event(evt)
    events: list[AgentEvent] = [evt]

    try:
        analyzer = DependencyAnalyzer()
        dep_findings, dep_context = analyzer.analyze(file_contents)

        # Build clean summary for RunResult
        if dep_findings:
            dep_summary = (
                f"Found {len(dep_findings)} dependency issues. "
                + "; ".join(f.title for f in dep_findings[:5])
            )
        else:
            dep_summary = "No dependency issues detected."

        done_evt = _event(run_id, EventType.AGENT_DONE, agent="dependency",
                           msg=f"✅ Dependency scan: {len(dep_findings)} issues found",
                           progress=1.0, fc=len(dep_findings))
        await store.push_event(done_evt)
        events.append(done_evt)

        return {
            "findings": dep_findings,
            "dependency_context": dep_context,
            "dependency_summary": dep_summary,
            "events": events,
        }

    except Exception as e:
        logger.error("Dependency analysis failed: %s", e)
        err_evt = _event(run_id, EventType.ERROR, agent="dependency",
                          msg=f"❌ Dependency analysis error: {e}")
        await store.push_event(err_evt)
        events.append(err_evt)
        return {
            "findings": [],
            "dependency_context": "",
            "dependency_summary": f"Dependency analysis failed: {e}",
            "events": events,
        }


# ── Router Node ──────────────────────────────────────────────────────

_ROUTER_SYSTEM_PROMPT = """You are an intelligent code analysis supervisor. Your job is to decide which analysis agents to run based on the codebase context.

Available agents:
- security: OWASP vulnerability scan, injection detection, hardcoded secrets
- tests: Generate framework-aware test files with run instructions
- speedup: Algorithmic complexity analysis, Big-O optimization, data structure redesign, memoization
- architecture: Design review, migration plans, dependency structure analysis
- prompt_quality: Meta-agent that validates other agents' prompt quality

ROUTING RULES — use these signals to decide:

1. **No test files detected** (no test_*.py, *_test.py, *.test.js, *.spec.ts, etc.) → MUST include "tests"
2. **SQL/database libraries detected** (sqlalchemy, psycopg2, mysql, sequelize, prisma, mongoose, etc.) → MUST include "security" (SQL injection risk)
3. **Large files detected** (files > 500 lines or > 20 files total) → include "architecture"
4. **Performance-sensitive patterns** (nested loops, recursive calls, large data processing, N+1 queries) → include "speedup"
5. **AI/LLM code detected** (openai, langchain, mistral, prompts, system_prompt) → include "prompt_quality"
6. **Web frameworks detected** (flask, django, fastapi, express, next) → MUST include "security"
7. **No clear signals** → default to ["security", "tests"]

Return ONLY valid JSON:
{
  "skills": ["security", "tests", "speedup", "architecture", "prompt_quality"],
  "reasoning": "Brief explanation of why each skill was selected based on the signals detected"
}

Be thorough — include ALL relevant agents. It is better to include an extra agent than to miss a relevant one."""


async def router_node(state: GraphState) -> dict:
    """Decide which agents to run using LLM with full repo + dependency context."""
    run_id = state["run_id"]
    mode = state.get("mode", RunMode.MANUAL)
    skills = list(state.get("selected_skills", []))

    if mode == RunMode.AUTO:
        # Build rich context for the LLM
        manifest_summary = state.get("repo_manifest_summary", "Unknown")
        dep_context = state.get("dependency_context", "")
        user_request = state.get("user_request", "")
        file_contents = state.get("file_contents", {})

        # Gather detection hints from actual file contents
        hints = _gather_routing_hints(file_contents, manifest_summary)

        user_prompt = f"""## User Request
{user_request if user_request else "Full analysis requested"}

## Repository Structure
{manifest_summary}

## Dependency Analysis
{dep_context if dep_context else "No dependency manifests found"}

## Detection Hints
{hints}

Based on ALL the above signals, decide which agents to run."""

        llm = get_llm()
        from backend.core.llm import TaskType
        result = await llm.generate_json(_ROUTER_SYSTEM_PROMPT, user_prompt, task_type=TaskType.ROUTING)

        raw = result.get("skills", [])
        skills = []
        for s in raw:
            try:
                skills.append(SkillType(s))
            except ValueError:
                pass
        if not skills:
            skills = [SkillType.SECURITY]  # fallback

    evt = _event(run_id, EventType.SUPERVISOR_STARTED, msg=f"Running agents: {[s.value for s in skills]}")
    await store.push_event(evt)

    return {
        "skills_to_run": skills,
        "events": [evt],
        "findings": [],
    }


def _gather_routing_hints(file_contents: dict[str, str], manifest: str) -> str:
    """Scan file contents for routing signals to feed to the LLM."""
    hints: list[str] = []

    file_paths = list(file_contents.keys())
    all_code = "\n".join(file_contents.values())

    # Test file detection
    test_patterns = ["test_", "_test.", ".test.", ".spec.", "tests/", "__tests__/"]
    has_tests = any(
        any(p in path.lower() for p in test_patterns)
        for path in file_paths
    )
    if not has_tests:
        hints.append("⚠️ NO TEST FILES DETECTED — strongly recommend including TestAgent")
    else:
        hints.append("✓ Test files found in repository")

    # SQL / DB detection
    sql_keywords = ["sqlalchemy", "psycopg", "mysql", "sqlite", "sequelize", "prisma",
                     "mongoose", "typeorm", "knex", "execute(", "cursor.execute",
                     "raw_query", "rawQuery", "SELECT ", "INSERT ", "UPDATE ", "DELETE "]
    sql_found = [k for k in sql_keywords if k.lower() in all_code.lower()]
    if sql_found:
        hints.append(f"⚠️ SQL/DATABASE PATTERNS DETECTED: {', '.join(sql_found[:5])} — SecurityAgent critical for injection scan")

    # Large files / complexity
    large_files = [p for p, c in file_contents.items() if len(c.split("\n")) > 500]
    if large_files:
        hints.append(f"⚠️ LARGE FILES DETECTED ({len(large_files)}): {', '.join(large_files[:3])} — consider ArchitectureAgent")
    if len(file_contents) > 20:
        hints.append(f"⚠️ LARGE CODEBASE ({len(file_contents)} files) — ArchitectureAgent recommended")

    # Performance patterns
    perf_patterns = ["for .* in .*:\n.*for", "while.*while", "O(n²)", "O(n^2)",
                     "time.sleep", "recursion", "recursive"]
    nested_loop_count = all_code.lower().count("for ") + all_code.lower().count("while ")
    if nested_loop_count > 10:
        hints.append(f"⚠️ MANY LOOP CONSTRUCTS ({nested_loop_count}) — AlgorithmicOptimizationAgent recommended for complexity analysis")

    # AI/LLM code
    ai_keywords = ["openai", "langchain", "mistral", "system_prompt", "user_prompt",
                    "generate_json", "chat.completion", "llm", "prompt"]
    ai_found = [k for k in ai_keywords if k.lower() in all_code.lower()]
    if ai_found:
        hints.append(f"✓ AI/LLM code detected: {', '.join(ai_found[:4])} — PromptQualityAgent may be useful")

    # Web framework detection
    web_keywords = ["flask", "django", "fastapi", "express", "router", "app.get(",
                     "app.post(", "@app.route", "APIRouter"]
    web_found = [k for k in web_keywords if k.lower() in all_code.lower()]
    if web_found:
        hints.append(f"⚠️ WEB FRAMEWORK DETECTED: {', '.join(web_found[:4])} — SecurityAgent essential")

    if not hints:
        hints.append("No strong signals detected — default routing recommended")

    return "\n".join(hints)


# ── Worker Nodes ─────────────────────────────────────────────────────

async def security_agent_node(state: GraphState) -> dict:
    """OWASP-style security analysis with defensive remediation."""
    from backend.agents.security_agent import SecurityAgent
    return await _run_agent(SecurityAgent, state)


async def test_agent_node(state: GraphState) -> dict:
    """Generate framework-aware tests with run instructions."""
    from backend.agents.test_agent import TestAgent
    return await _run_agent(TestAgent, state)


async def algorithmic_opt_agent_node(state: GraphState) -> dict:
    """Algorithmic complexity analysis with Big-O optimization."""
    from backend.agents.speedup_agent import AlgorithmicOptimizationAgent
    return await _run_agent(AlgorithmicOptimizationAgent, state)


async def architecture_agent_node(state: GraphState) -> dict:
    """Design review with migration plan and ASCII diagrams."""
    from backend.agents.architecture_agent import ArchitectureAgent
    return await _run_agent(ArchitectureAgent, state)


async def prompt_quality_agent_node(state: GraphState) -> dict:
    """Meta-agent: improve other agents' prompts and validate outputs."""
    from backend.agents.prompt_quality_agent import PromptQualityAgent
    return await _run_agent(PromptQualityAgent, state)


async def _run_agent(agent_cls, state: GraphState) -> dict:
    """Shared runner for all worker agents."""
    run_id = state["run_id"]
    llm = get_llm()
    agent = agent_cls(llm=llm, run_id=run_id)
    name = agent.AGENT_NAME

    started_evt = _event(run_id, EventType.AGENT_STARTED, agent=name, msg=f"Starting {name} analysis...")
    await store.push_event(started_evt)
    events: list[AgentEvent] = [started_evt]

    try:
        files = state.get("file_contents", {})
        manifest_summary = state.get("repo_manifest_summary", "")

        # Inject dependency context for richer agent analysis
        dep_context = state.get("dependency_context", "")
        if dep_context:
            manifest_summary += f"\n\n--- Dependency Analysis ---\n{dep_context}"

        findings = await agent.analyze(files, manifest_summary)

        done_evt = _event(run_id, EventType.AGENT_DONE, agent=name,
                          msg=f"{name} complete: {len(findings)} findings",
                          progress=1.0, fc=len(findings))
        await store.push_event(done_evt)
        events.append(done_evt)
        return {"findings": findings, "events": events}

    except Exception as e:
        err_evt = _event(run_id, EventType.ERROR, agent=name, msg=f"{name} error: {str(e)}")
        await store.push_event(err_evt)
        events.append(err_evt)
        return {"findings": [], "events": events}


# ── Critic Node ──────────────────────────────────────────────────────

async def critic_node(state: GraphState) -> dict:
    """Self-reflection: evaluate all findings, remove weak ones, adjust confidence."""
    from backend.agents.critic_agent import CriticAgent

    run_id = state["run_id"]
    llm = get_llm()
    critic = CriticAgent(llm=llm, run_id=run_id)

    findings = state.get("findings", [])
    file_contents = state.get("file_contents", {})
    manifest_summary = state.get("repo_manifest_summary", "")

    started_evt = _event(run_id, EventType.AGENT_STARTED, agent="critic",
                          msg=f"Critic reviewing {len(findings)} findings...")
    await store.push_event(started_evt)
    events: list[AgentEvent] = [started_evt]

    try:
        refined_findings, critique_summary = await critic.critique(
            findings, file_contents, manifest_summary,
        )

        done_evt = _event(run_id, EventType.AGENT_DONE, agent="critic",
                           msg=f"Critic done: {len(refined_findings)}/{len(findings)} kept",
                           progress=1.0, fc=len(refined_findings))
        await store.push_event(done_evt)
        events.append(done_evt)

        return {
            "findings": refined_findings,
            "critique_summary": critique_summary,
            "events": events,
        }

    except Exception as e:
        err_evt = _event(run_id, EventType.ERROR, agent="critic",
                          msg=f"Critic error: {e}. Findings passed through.")
        await store.push_event(err_evt)
        events.append(err_evt)
        return {
            "findings": findings,
            "critique_summary": f"Critic failed: {e}",
            "events": events,
        }


# ── Remediation Node ─────────────────────────────────────────────────

async def remediation_node(state: GraphState) -> dict:
    """
    Auto-fix engine: generate production-ready code fixes for validated findings.
    Runs after critic to ensure only validated findings get auto-fixes.
    """
    from backend.agents.remediation_agent import RemediationAgent

    run_id = state["run_id"]
    llm = get_llm()
    remediator = RemediationAgent(llm=llm, run_id=run_id)

    findings = state.get("findings", [])
    file_contents = state.get("file_contents", {})
    manifest_summary = state.get("repo_manifest_summary", "")

    started_evt = _event(run_id, EventType.AGENT_STARTED, agent="remediation",
                          msg=f"🔧 Remediation engine processing {len(findings)} findings...")
    await store.push_event(started_evt)
    events: list[AgentEvent] = [started_evt]

    try:
        updated_findings, remediation_summary = await remediator.remediate(
            findings, file_contents, manifest_summary,
        )

        fix_count = sum(1 for f in updated_findings if f.auto_fix)
        done_evt = _event(run_id, EventType.AGENT_DONE, agent="remediation",
                           msg=f"✅ Remediation: {fix_count} production-ready fixes generated",
                           progress=1.0, fc=fix_count)
        await store.push_event(done_evt)
        events.append(done_evt)

        return {
            "findings": updated_findings,
            "remediation_summary": remediation_summary,
            "events": events,
        }

    except Exception as e:
        err_evt = _event(run_id, EventType.ERROR, agent="remediation",
                          msg=f"Remediation error: {e}. Findings passed through.")
        await store.push_event(err_evt)
        events.append(err_evt)
        return {
            "findings": findings,
            "remediation_summary": f"Remediation failed: {e}",
            "events": events,
        }


# ── Strategic Planner Node ───────────────────────────────────────────

async def strategic_planner_node(state: GraphState) -> dict:
    """
    Risk prioritization and rollout strategy.
    Clusters related issues, estimates effort, builds phased deployment plan.
    Runs after remediation so it knows which findings have auto-fixes available.
    """
    from backend.agents.strategic_planner import StrategicPlannerAgent

    run_id = state["run_id"]
    llm = get_llm()
    planner = StrategicPlannerAgent(llm=llm, run_id=run_id)

    findings = state.get("findings", [])

    started_evt = _event(run_id, EventType.AGENT_STARTED, agent="strategic_planner",
                          msg=f"📊 Strategic planner analyzing {len(findings)} findings...")
    await store.push_event(started_evt)
    events: list[AgentEvent] = [started_evt]

    try:
        roadmap = await planner.plan(findings)

        done_evt = _event(run_id, EventType.AGENT_DONE, agent="strategic_planner",
                           msg=f"✅ Roadmap: {roadmap.total_clusters} clusters, "
                               f"{len(roadmap.rollout_phases)} phases, "
                               f"{len(roadmap.quick_wins)} quick wins",
                           progress=1.0, fc=roadmap.total_clusters)
        await store.push_event(done_evt)
        events.append(done_evt)

        return {
            "roadmap": roadmap,
            "events": events,
            "findings": [],  # Don't double-add findings
        }

    except Exception as e:
        err_evt = _event(run_id, EventType.ERROR, agent="strategic_planner",
                          msg=f"Strategic planning error: {e}.")
        await store.push_event(err_evt)
        events.append(err_evt)
        return {
            "roadmap": None,
            "events": events,
            "findings": [],
        }


# ── Aggregator Node ──────────────────────────────────────────────────

# Severity deduction map
_SEVERITY_PENALTY = {
    "critical": 15,
    "high": 8,
    "medium": 3,
    "low": 1,
    "info": 0,
}

# Agent → score category mapping
_AGENT_SCORE_MAP = {
    "security": "security",
    "dependency": "security",          # dependency issues affect security score
    "algorithmic_opt": "performance",
    "architecture": "architecture",
    "tests": "tests",
    "prompt_quality": "architecture",  # meta-agent rolls into architecture
}


def _compute_health_scores(
    findings: list, skills_run: list
) -> dict:
    """
    Compute per-category health scores (0–100).

    Formula per category:
      - Start at 100
      - Deduct: 15×critical, 8×high, 3×medium, 1×low
      - Architecture penalty: if architecture findings > 3 → extra −5
      - Tests: if test agent didn't run → cap at 40
    """
    from backend.schemas import HealthScores, SkillType

    # Bucket findings by score category
    buckets: dict[str, list] = {
        "security": [],
        "performance": [],
        "architecture": [],
        "tests": [],
    }
    for f in findings:
        category = _AGENT_SCORE_MAP.get(f.agent, "architecture")
        if category in buckets:
            buckets[category].append(f)

    # Compute raw score per category
    scores: dict[str, int] = {}
    for category, cat_findings in buckets.items():
        score = 100
        for f in cat_findings:
            penalty = _SEVERITY_PENALTY.get(f.severity.value, 0)
            score -= penalty
        scores[category] = max(0, score)

    # Architecture penalty: if > 3 architecture findings, subtract extra 5
    if len(buckets["architecture"]) > 3:
        scores["architecture"] = max(0, scores["architecture"] - 5)

    # Test readiness: if test agent didn't run, cap at 40
    skill_values = [s.value if hasattr(s, "value") else str(s) for s in skills_run]
    if "tests" not in skill_values:
        scores["tests"] = min(scores["tests"], 40)

    # Overall = weighted average
    overall = int(
        scores["security"] * 0.35
        + scores["performance"] * 0.25
        + scores["architecture"] * 0.25
        + scores["tests"] * 0.15
    )
    overall = max(0, min(100, overall))

    return HealthScores(
        security=scores["security"],
        performance=scores["performance"],
        architecture=scores["architecture"],
        tests=scores["tests"],
        overall=overall,
    )


async def aggregator_node(state: GraphState) -> dict:
    """Consolidate findings, compute health scores, include remediation & roadmap, emit supervisor_done."""
    from backend.schemas import HealthScores

    run_id = state["run_id"]
    findings = state.get("findings", [])
    files_count = len(state.get("file_contents", {}))
    skills = state.get("skills_to_run", state.get("selected_skills", []))
    critique_summary = state.get("critique_summary", "")
    remediation_summary = state.get("remediation_summary", "")
    roadmap = state.get("roadmap", None)

    # ── Health scores ────────────────────────────────────────────────
    health = _compute_health_scores(findings, skills)

    # ── Summary ──────────────────────────────────────────────────────
    sev_counts: dict[str, int] = {}
    for f in findings:
        sev_counts[f.severity.value] = sev_counts.get(f.severity.value, 0) + 1

    fix_count = sum(1 for f in findings if f.auto_fix)

    sev_str = ", ".join(f"{k}: {v}" for k, v in sorted(sev_counts.items()))
    summary = (
        f"Analyzed {files_count} files with {len(skills)} agents. "
        f"Found {len(findings)} findings after critic review ({sev_str}).\n"
        f"Auto-fixes generated: {fix_count}.\n\n"
        f"Health Scores — "
        f"Security: {health.security}, "
        f"Performance: {health.performance}, "
        f"Architecture: {health.architecture}, "
        f"Tests: {health.tests}, "
        f"Overall: {health.overall}"
    )
    if critique_summary:
        summary += f"\n\nCritic: {critique_summary}"
    if remediation_summary:
        summary += f"\n\nRemediation: {remediation_summary}"
    if roadmap and roadmap.executive_summary:
        summary += f"\n\nStrategic Plan: {roadmap.executive_summary}"

    done_msg = (
        f"Analysis complete: {len(findings)} findings | "
        f"{fix_count} auto-fixes | Health: {health.overall}/100"
    )
    if roadmap:
        done_msg += f" | {roadmap.total_clusters} clusters, {len(roadmap.rollout_phases)} phases"

    done_evt = _event(run_id, EventType.SUPERVISOR_DONE, msg=done_msg)
    await store.push_event(done_evt)

    return {
        "summary": summary,
        "health_scores": health,
        "total_files_analyzed": files_count,
        "events": [done_evt],
        "findings": [],  # Don't double-add
    }

