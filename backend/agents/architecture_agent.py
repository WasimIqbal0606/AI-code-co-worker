"""
ArchitectureAgent — Design review with structured migration plan + ASCII diagrams.
"""

from __future__ import annotations

import asyncio

from backend.agents.base_agent import BaseAgent
from backend.schemas import (
    EventType, Finding, Severity,
    ArchitecturePlan,
)

SYSTEM_PROMPT = """You are a senior software architect conducting a design review.
Provide actionable architectural guidance with a concrete migration plan.

Return ONLY valid JSON:
{
  "findings": [
    {
      "title": "Architecture issue title",
      "severity": "high|medium|low|info",
      "confidence": 0.85,
      "file_path": "primary file or module path",
      "line_range": [start, end],
      "evidence": "Code or structure demonstrating the issue",
      "architecture_plan": {
        "current_summary": "Current architecture: describe modules, coupling patterns, and identified anti-patterns. Example: 'Monolithic app.py (800 lines) handles routing, business logic, and DB access. No dependency injection. Circular imports between models and utils.'",
        "proposed_changes": "Target architecture: describe the improved structure. Example: 'Split into routes/, services/, repositories/ layers. Introduce interfaces for DB access. Use dependency injection container.'",
        "risks_tradeoffs": "What could go wrong, what you're trading. Example: 'More files to maintain. Service layer adds indirection. Risk of over-engineering for small projects.'",
        "refactor_steps": [
          "Step 1: Extract DB queries into repositories/user_repo.py",
          "Step 2: Create services/user_service.py with business logic",
          "Step 3: Slim down routes to only handle HTTP concerns",
          "Step 4: Add interfaces (Protocol classes) for repositories",
          "Step 5: Wire up dependency injection in main.py"
        ],
        "acceptance_criteria": [
          "No file exceeds 200 lines",
          "Zero circular imports",
          "Each layer only depends on the layer below it",
          "All existing tests still pass"
        ],
        "ascii_diagram": "A text-based architecture diagram showing the proposed structure. Use boxes and arrows. Example:\\n┌──────────┐   ┌──────────┐\\n│  Routes  │──→│ Services │\\n└──────────┘   └────┬─────┘\\n                    │\\n              ┌─────▼─────┐\\n              │   Repos    │\\n              └─────┬─────┘\\n                    │\\n              ┌─────▼─────┐\\n              │    DB      │\\n              └───────────┘"
      },
      "explain_steps": [
        "Mapped module dependencies",
        "Identified God class in app.py",
        "Designed layered architecture",
        "Created incremental migration plan"
      ]
    }
  ]
}

Rules:
- Focus on INCREMENTAL refactoring, not big-bang rewrites
- Each step should be independently deployable
- Include acceptance criteria that are testable
- ASCII diagrams should show component relationships
- Max 6 findings"""


class ArchitectureAgent(BaseAgent):
    AGENT_NAME = "architecture"

    async def analyze(self, files: dict[str, str], manifest_summary: str) -> list[Finding]:
        total = len(files)
        await self.emit(EventType.AGENT_STARTED, f"🏗️ Starting architecture review — {total} files")

        # ── Progressive structural analysis ────────────────────
        scanned = 0
        modules = {}       # dir → file count
        god_files = []      # files > 300 lines
        import_patterns = []

        for path, content in files.items():
            scanned += 1
            lines = content.split("\n")
            line_count = len(lines)

            # Track module structure
            parts = path.split("/")
            if len(parts) > 1:
                modules[parts[0]] = modules.get(parts[0], 0) + 1

            # Detect god classes/files
            if line_count > 300:
                god_files.append((path, line_count))
                await self.emit(
                    EventType.AGENT_PROGRESS,
                    f"⚠️ Large file: {path} ({line_count} lines) — potential God class",
                    progress=round(scanned / total * 0.2, 2),
                )

            # Detect circular import risk
            import_count = content.count("import ") + content.count("from ")
            if import_count > 15:
                import_patterns.append(path)

            if scanned % max(1, total // 3) == 0 or scanned == total:
                await self.emit(
                    EventType.AGENT_PROGRESS,
                    f"Mapping structure {scanned}/{total}: {path}",
                    progress=round(scanned / total * 0.2, 2),
                )
                await asyncio.sleep(0)

        # Report structural analysis
        if modules:
            mod_summary = ", ".join(f"{k}/ ({v})" for k, v in sorted(modules.items(), key=lambda x: -x[1])[:5])
            await self.emit(
                EventType.AGENT_PROGRESS,
                f"📁 Module structure: {mod_summary}",
                progress=0.25,
            )

        if god_files:
            god_list = ", ".join(f"{p} ({n}L)" for p, n in god_files[:3])
            await self.emit(
                EventType.AGENT_PROGRESS,
                f"🔴 {len(god_files)} oversized files detected: {god_list}",
                progress=0.28,
            )

        if import_patterns:
            await self.emit(
                EventType.AGENT_PROGRESS,
                f"⚠️ {len(import_patterns)} files with heavy imports — circular dependency risk",
                progress=0.3,
            )

        # ── LLM analysis ──────────────────────────────────────
        await self.emit(EventType.AGENT_PROGRESS, "🧠 Analyzing architecture patterns via Mistral...", progress=0.4)

        file_content = self._build_file_content(files)
        user_prompt = f"""Repo structure:\n{manifest_summary}\n\nCode files:\n{file_content}"""

        try:
            from backend.core.llm import TaskType
            result = await self.llm.generate_json(SYSTEM_PROMPT, user_prompt, task_type=TaskType.ARCHITECTURE)

            await self.emit(EventType.AGENT_PROGRESS, "📋 Building migration plans and diagrams...", progress=0.85)
            findings = self._parse_findings(result)

            for f in findings:
                await self.emit(
                    EventType.AGENT_PROGRESS,
                    f"🏗️ Found: {f.title} in {f.file_path}",
                    progress=0.9,
                    findings_count=len(findings),
                )
        except Exception as e:
            await self.emit(EventType.AGENT_PROGRESS, f"❌ Error: {str(e)}", progress=1.0)
            findings = []

        await self.emit(
            EventType.AGENT_DONE,
            f"✅ Architecture review complete — {len(findings)} suggestions with migration plans",
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
            arch_plan = None
            ap = f.get("architecture_plan", {})
            if ap:
                arch_plan = ArchitecturePlan(
                    current_summary=ap.get("current_summary", ""),
                    proposed_changes=ap.get("proposed_changes", ""),
                    risks_tradeoffs=ap.get("risks_tradeoffs", ""),
                    refactor_steps=ap.get("refactor_steps", []),
                    acceptance_criteria=ap.get("acceptance_criteria", []),
                    ascii_diagram=ap.get("ascii_diagram", ""),
                )

            fp = f.get("file_path", "")
            file_path = ", ".join(fp) if isinstance(fp, list) else str(fp)

            findings.append(Finding(
                id=self._make_finding_id(),
                agent=self.AGENT_NAME,
                severity=Severity(f.get("severity", "medium")),
                confidence=self._normalize_confidence(f.get("confidence", 0.7)),
                title=f.get("title", "Architecture Suggestion"),
                description=ap.get("proposed_changes", f.get("description", "")),
                file_path=file_path,
                line_range=f.get("line_range"),
                evidence=f.get("evidence", ""),
                recommendation=ap.get("proposed_changes", ""),
                explain_steps=f.get("explain_steps", []),
                architecture_plan=arch_plan,
            ))
        return findings
