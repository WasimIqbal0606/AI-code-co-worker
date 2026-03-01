"""
PromptQualityAgent — Meta-agent that improves OTHER agents' prompts.
Treats prompt optimization as a system component, not a user tool.
"""

from __future__ import annotations

from backend.agents.base_agent import BaseAgent
from backend.schemas import EventType, Finding, Patch, Severity

SYSTEM_PROMPT = """You are a prompt engineering expert and meta-agent.
Your job is to analyze BOTH the user's code AND the system's own agent prompts for quality.

Two-part analysis:

PART 1 - User Code Prompts:
Find LLM prompts in the codebase and evaluate against best practices.

PART 2 - System Prompt Recommendations:
Based on the code you've seen, suggest how AI analysis prompts could be improved
for better structured output, fewer hallucinations, and higher reliability.

Return ONLY valid JSON:
{
  "findings": [
    {
      "title": "Prompt issue title",
      "severity": "high|medium|low|info",
      "confidence": 0.85,
      "file_path": "relative/path/to/file",
      "line_range": [start, end],
      "evidence": "The current prompt text",
      "recommendation": "Improved prompt with explanation",
      "category": "user_code|system_meta",
      "prompt_version": "v1",
      "improved_prompt": "The complete improved prompt text",
      "validation_rules": [
        "Output must be valid JSON",
        "Must include severity field",
        "confidence must be 0.0-1.0"
      ],
      "patch_diff": "Unified diff showing the prompt change",
      "explain_steps": [
        "Found vague system prompt missing output format",
        "Added JSON schema enforcement",
        "Added few-shot example for edge cases",
        "Added guardrails against prompt injection"
      ]
    }
  ],
  "system_recommendations": {
    "reliability_improvements": [
      "Add JSON schema validation to all agent outputs",
      "Use structured output mode (response_format: json_object)"
    ],
    "prompt_versioning_note": "Track prompt versions (v1, v2, v3) to measure improvement"
  }
}

Focus on:
- Missing output format specifications
- Vague or ambiguous instructions
- No few-shot examples where helpful
- Prompt injection vulnerabilities
- Missing constraints/guardrails
- Temperature parameter suggestions
- Chain-of-thought opportunities
- Structured output enforcement
Max 8 findings."""


class PromptQualityAgent(BaseAgent):
    AGENT_NAME = "prompt_quality"

    async def analyze(self, files: dict[str, str], manifest_summary: str) -> list[Finding]:
        import asyncio

        total = len(files)
        await self.emit(EventType.AGENT_STARTED, f"✨ Starting prompt quality meta-analysis — {total} files")

        # ── Progressive scanning for prompt patterns ────────────
        prompt_files = []
        scanned = 0

        for path, content in files.items():
            scanned += 1
            lower = content.lower()

            # Detect files with prompts
            has_prompts = any(k in lower for k in [
                "system_prompt", "user_prompt", "system_message",
                "prompt =", "prompt=", "instruction =", "openai",
                "generate_json", "generate_text", "chat.completion",
                "langchain", "mistral",
            ])
            if has_prompts:
                prompt_files.append(path)
                await self.emit(
                    EventType.AGENT_PROGRESS,
                    f"🔍 Found LLM/prompt code: {path}",
                    progress=round(scanned / total * 0.25, 2),
                )

            if scanned % max(1, total // 3) == 0:
                await self.emit(
                    EventType.AGENT_PROGRESS,
                    f"Scanning {scanned}/{total}: {path}",
                    progress=round(scanned / total * 0.25, 2),
                )
                await asyncio.sleep(0)

        if prompt_files:
            await self.emit(
                EventType.AGENT_PROGRESS,
                f"📝 Found {len(prompt_files)} files with prompt patterns: {', '.join(prompt_files[:4])}",
                progress=0.3,
            )
        else:
            await self.emit(
                EventType.AGENT_PROGRESS,
                "ℹ️ No explicit prompt files — analyzing code structure for meta-improvements",
                progress=0.3,
            )

        # ── LLM analysis ──────────────────────────────────────
        await self.emit(EventType.AGENT_PROGRESS, "🧠 Evaluating prompt quality via Mistral...", progress=0.4)

        file_content = self._build_file_content(files)
        user_prompt = f"""Repo structure:\n{manifest_summary}\n\nCode files:\n{file_content}"""

        try:
            from backend.core.llm import TaskType
            result = await self.llm.generate_json(SYSTEM_PROMPT, user_prompt, task_type=TaskType.PROMPT_ANALYSIS)

            await self.emit(EventType.AGENT_PROGRESS, "📋 Building prompt improvement suggestions...", progress=0.85)
            findings = self._parse_findings(result)

            for f in findings:
                await self.emit(
                    EventType.AGENT_PROGRESS,
                    f"✨ Found: {f.title}",
                    progress=0.9,
                    findings_count=len(findings),
                )
        except Exception as e:
            await self.emit(EventType.AGENT_PROGRESS, f"❌ Error: {str(e)}", progress=1.0)
            findings = []

        await self.emit(
            EventType.AGENT_DONE,
            f"✅ Prompt analysis complete — {len(findings)} improvements found",
            progress=1.0,
            findings_count=len(findings),
        )
        return findings

    def _build_file_content(self, files: dict[str, str]) -> str:
        parts = []
        for path, content in files.items():
            parts.append(f"--- {path} ---\n{content[:3000]}\n")
        return "\n".join(parts)

    def _parse_findings(self, result: dict) -> list[Finding]:
        findings = []
        for f in result.get("findings", []):
            patch = None
            if f.get("patch_diff"):
                patch = Patch(
                    file_path=f.get("file_path", ""),
                    diff=f["patch_diff"],
                    description=f.get("title", ""),
                )
            elif f.get("improved_prompt"):
                # Show the improved prompt as a "patch"
                patch = Patch(
                    file_path=f.get("file_path", "prompt"),
                    diff=f"# Improved Prompt (v2)\n\n{f['improved_prompt']}",
                    description=f"Prompt improvement: {f.get('title', '')}",
                )

            desc = f.get("recommendation", "")
            if f.get("validation_rules"):
                desc += "\n\nValidation rules:\n" + "\n".join(f"  • {r}" for r in f["validation_rules"])

            findings.append(Finding(
                id=self._make_finding_id(),
                agent=self.AGENT_NAME,
                severity=Severity(f.get("severity", "medium")),
                confidence=self._normalize_confidence(f.get("confidence", 0.7)),
                title=f.get("title", "Prompt Improvement"),
                description=desc,
                file_path=f.get("file_path", ""),
                line_range=f.get("line_range"),
                evidence=f.get("evidence", ""),
                recommendation=f.get("recommendation", ""),
                patch=patch,
                explain_steps=f.get("explain_steps", []),
            ))
        return findings
