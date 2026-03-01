"""
CriticAgent — Self-reflection layer that evaluates and refines findings.
Runs after all worker agents, before final aggregation.
Removes weak/hallucinated findings, adjusts confidence, validates severity.
"""

from __future__ import annotations

import logging
from backend.agents.base_agent import BaseAgent
from backend.schemas import EventType, Finding, Severity

logger = logging.getLogger(__name__)

CRITIC_SYSTEM_PROMPT = """You are a senior code-review critic and quality-assurance auditor.
Your job is to evaluate findings produced by automated AI agents that analyzed source code.

For EACH finding, evaluate:

1. **Evidence Check**: Does the finding reference real code evidence (variable names, function calls, line numbers)?
   - If evidence is empty or vague ("this could be an issue"), mark as REMOVE.

2. **Patch Logic Check**: If a patch/diff is provided, does it logically fix the described issue?
   - If the patch is nonsensical, contradicts the finding, or introduces new bugs, mark for DOWNGRADE.

3. **Severity Consistency**: Does the assigned severity match the actual impact?
   - "info" level issues marked "critical" should be downgraded.
   - Actual RCE / SQL injection / auth bypass should stay critical/high.

4. **Hallucination Detection**: Is the finding describing something that clearly doesn't exist in the provided code?
   - References to files, functions, or patterns not in the code = hallucination → REMOVE.

5. **Vagueness Filter**: Findings with only generic descriptions and no specific code references are too vague → REMOVE.

6. **Confidence Adjustment**: Based on evidence strength, adjust confidence:
   - Strong evidence (exact code snippet, line numbers, clear vulnerability) → keep or raise (0.8-1.0)
   - Moderate evidence (right area, but slightly speculative) → moderate (0.5-0.7)
   - Weak evidence (generic, no specifics) → low (0.2-0.4) or REMOVE

Return ONLY valid JSON:
{
  "critiqued_findings": [
    {
      "finding_id": "original finding id",
      "action": "keep|remove|downgrade_severity|adjust_confidence",
      "adjusted_severity": "critical|high|medium|low|info",
      "adjusted_confidence": 0.85,
      "critique_reason": "Why this action was taken",
      "is_hallucination": false
    }
  ],
  "critique_summary": "Overall quality assessment of the findings batch",
  "total_reviewed": 10,
  "total_removed": 2,
  "total_adjusted": 3,
  "quality_score": 0.75
}

Be strict but fair. Only remove findings that are clearly weak, vague, or hallucinated.
Keep any finding that has genuine code evidence and a plausible security/quality concern."""


class CriticAgent(BaseAgent):
    """Self-reflection agent that validates and refines findings from all worker agents."""

    AGENT_NAME = "critic"

    async def analyze(self, files: dict[str, str], manifest_summary: str) -> list[Finding]:
        """Not used directly — CriticAgent uses critique() instead."""
        return []

    async def critique(
        self,
        findings: list[Finding],
        file_contents: dict[str, str],
        manifest_summary: str,
    ) -> tuple[list[Finding], str]:
        """
        Evaluate all findings, remove weak ones, adjust confidence/severity.

        Returns:
            (refined_findings, critique_summary)
        """
        if not findings:
            return [], "No findings to critique."

        await self.emit(
            EventType.AGENT_STARTED,
            f"Critic reviewing {len(findings)} findings for quality...",
        )

        # Build the prompt with findings + source code context
        findings_text = self._serialize_findings(findings)
        code_context = self._build_code_context(file_contents)

        user_prompt = (
            f"## Findings to evaluate ({len(findings)} total):\n\n"
            f"{findings_text}\n\n"
            f"## Source code context:\n\n"
            f"{code_context}\n\n"
            f"## Repo structure:\n{manifest_summary}\n\n"
            f"Evaluate each finding. Be strict about hallucinations and vague findings."
        )

        await self.emit(
            EventType.AGENT_PROGRESS,
            "Checking evidence, patches, severity consistency...",
            progress=0.3,
        )

        try:
            from backend.core.llm import TaskType
            result = await self.llm.generate_json(CRITIC_SYSTEM_PROMPT, user_prompt, task_type=TaskType.CRITIC_REVIEW)
            refined, summary = self._apply_critique(findings, result)
        except Exception as e:
            logger.error(f"CriticAgent failed: {e}")
            await self.emit(
                EventType.AGENT_PROGRESS,
                f"Critic error: {e}. Passing findings through unmodified.",
                progress=1.0,
            )
            return findings, f"Critic failed: {e}. Findings passed through."

        await self.emit(
            EventType.AGENT_DONE,
            f"Critic done: {len(refined)}/{len(findings)} findings kept. {summary[:100]}",
            progress=1.0,
            findings_count=len(refined),
        )

        return refined, summary

    def _serialize_findings(self, findings: list[Finding]) -> str:
        """Convert findings to readable text for the critic prompt."""
        parts = []
        for i, f in enumerate(findings, 1):
            patch_info = ""
            if f.patch:
                patch_info = f"\n  Patch: {f.patch.diff[:200]}..."

            parts.append(
                f"### Finding {i} (ID: {f.id})\n"
                f"  Agent: {f.agent}\n"
                f"  Title: {f.title}\n"
                f"  Severity: {f.severity.value}\n"
                f"  Confidence: {f.confidence}\n"
                f"  File: {f.file_path}\n"
                f"  Lines: {f.line_range}\n"
                f"  Description: {f.description}\n"
                f"  Evidence: {f.evidence}\n"
                f"  Recommendation: {f.recommendation}"
                f"{patch_info}\n"
            )
        return "\n".join(parts)

    def _build_code_context(self, files: dict[str, str]) -> str:
        """Build truncated code context for the critic to cross-reference."""
        parts = []
        for path, content in files.items():
            lines = content.split("\n")[:150]  # First 150 lines per file
            numbered = "\n".join(f"{i+1}: {line}" for i, line in enumerate(lines))
            parts.append(f"--- {path} ---\n{numbered}\n")
        return "\n".join(parts)

    def _apply_critique(
        self, original_findings: list[Finding], critique: dict
    ) -> tuple[list[Finding], str]:
        """Apply the critic's recommendations to the findings list."""
        # Build lookup by finding ID
        findings_map = {f.id: f for f in original_findings}
        critiqued = critique.get("critiqued_findings", [])

        # Track which IDs the critic reviewed
        reviewed_ids = set()
        refined: list[Finding] = []

        for c in critiqued:
            fid = c.get("finding_id", "")
            action = c.get("action", "keep").lower()
            reviewed_ids.add(fid)

            if fid not in findings_map:
                continue

            finding = findings_map[fid]

            if action == "remove":
                logger.info(f"Critic REMOVED finding {fid}: {c.get('critique_reason', '')}")
                continue

            # Apply adjustments
            if action in ("downgrade_severity", "adjust_confidence"):
                # Adjust severity if provided
                new_sev = c.get("adjusted_severity")
                if new_sev:
                    try:
                        finding = finding.model_copy(update={"severity": Severity(new_sev)})
                    except ValueError:
                        pass  # keep original severity

                # Adjust confidence if provided
                new_conf = c.get("adjusted_confidence")
                if new_conf is not None:
                    finding = finding.model_copy(
                        update={"confidence": max(0.0, min(1.0, float(new_conf)))}
                    )

                logger.info(
                    f"Critic ADJUSTED finding {fid}: "
                    f"severity={finding.severity.value}, confidence={finding.confidence}"
                )

            refined.append(finding)

        # Keep any findings the critic didn't review (pass-through)
        for fid, finding in findings_map.items():
            if fid not in reviewed_ids:
                refined.append(finding)

        summary = critique.get(
            "critique_summary",
            f"Reviewed {len(critiqued)} findings, kept {len(refined)}/{len(original_findings)}.",
        )
        quality_score = critique.get("quality_score", "N/A")
        summary += f" Quality score: {quality_score}"

        return refined, summary
