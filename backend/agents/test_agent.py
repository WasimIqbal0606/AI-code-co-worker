"""
TestAgent — Framework-aware test generation with run instructions.
Detects language/framework, generates parametrized tests, provides run commands.
"""

from __future__ import annotations

import asyncio

from backend.agents.base_agent import BaseAgent
from backend.schemas import (
    EventType, Finding, Patch, Severity,
    TestRunInstructions,
)

SYSTEM_PROMPT = """You are a senior test engineer. Generate minimal, runnable unit tests.

Step 1: Detect the language and test framework:
- Python → pytest (use @pytest.mark.parametrize for multiple cases)
- JavaScript/TypeScript → jest
- Java → JUnit
- Go → testing package

Step 2: For each key module, generate a complete test file.

Return ONLY valid JSON:
{
  "findings": [
    {
      "title": "Test coverage for [module name]",
      "severity": "medium|low|info",
      "confidence": 0.85,
      "file_path": "path/to/source/file/being/tested",
      "line_range": [start, end],
      "evidence": "Key functions/classes that need testing",
      "recommendation": "What scenarios are tested and why",
      "test_code": "Complete runnable test file content. For pytest, use @pytest.mark.parametrize to cover multiple inputs cleanly. Include imports, fixtures, and assertions.",
      "test_file_name": "tests/test_module_name.py",
      "test_instructions": {
        "framework": "pytest",
        "install_command": "pip install pytest",
        "run_command": "pytest tests/test_module_name.py -v",
        "notes": "Run with -v for verbose output. Add --cov for coverage."
      },
      "explain_steps": [
        "Identified 3 public functions in utils.py",
        "Generated parametrized tests for edge cases",
        "Added error handling test cases"
      ]
    }
  ]
}

Rules:
- Tests MUST be complete and runnable
- Use parametrize for multiple test cases
- Test edge cases: empty inputs, None, boundary values, errors
- Include docstrings explaining what each test verifies
- Max 8 findings"""


class TestAgent(BaseAgent):
    AGENT_NAME = "tests"

    async def analyze(self, files: dict[str, str], manifest_summary: str) -> list[Finding]:
        total = len(files)
        await self.emit(EventType.AGENT_STARTED, f"🧪 Starting test generation — {total} files to analyze")

        # ── Progressive file scanning ──────────────────────────
        testable_files = []
        detected_frameworks = set()
        scanned = 0

        for path, content in files.items():
            scanned += 1
            lower_path = path.lower()
            lower_content = content.lower()

            # Detect language/framework
            if lower_path.endswith(".py"):
                detected_frameworks.add("Python")
                if "pytest" in lower_content or "unittest" in lower_content:
                    detected_frameworks.add("pytest")
            elif lower_path.endswith((".js", ".ts", ".jsx", ".tsx")):
                detected_frameworks.add("JavaScript/TypeScript")
                if "jest" in lower_content:
                    detected_frameworks.add("jest")

            # Identify testable files (skip tests themselves)
            is_test = any(p in lower_path for p in ["test_", "_test.", ".test.", ".spec.", "__tests__"])
            if not is_test and lower_path.endswith((".py", ".js", ".ts", ".jsx", ".tsx")):
                # Count functions/classes
                func_count = content.count("def ") + content.count("function ") + content.count("=> ")
                if func_count > 0:
                    testable_files.append((path, func_count))

            if scanned % max(1, total // 3) == 0 or scanned == total:
                await self.emit(
                    EventType.AGENT_PROGRESS,
                    f"Scanning file {scanned}/{total}: {path}",
                    progress=round(scanned / total * 0.25, 2),
                )
                await asyncio.sleep(0)

        # Report framework detection
        if detected_frameworks:
            await self.emit(
                EventType.AGENT_PROGRESS,
                f"🔧 Detected frameworks: {', '.join(sorted(detected_frameworks))}",
                progress=0.28,
            )

        # Report testable files
        testable_files.sort(key=lambda x: x[1], reverse=True)
        top_files = testable_files[:5]
        if top_files:
            file_list = ", ".join(f"{p} ({n} funcs)" for p, n in top_files)
            await self.emit(
                EventType.AGENT_PROGRESS,
                f"📝 Found {len(testable_files)} testable files — Top: {file_list}",
                progress=0.32,
            )

        # ── LLM call ───────────────────────────────────────────
        await self.emit(EventType.AGENT_PROGRESS, "🧠 Generating parametrized tests via Mistral...", progress=0.4)

        file_content = self._build_file_content(files)
        user_prompt = f"""Repo structure:\n{manifest_summary}\n\nCode files:\n{file_content}"""

        try:
            from backend.core.llm import TaskType
            result = await self.llm.generate_json(SYSTEM_PROMPT, user_prompt, task_type=TaskType.TEST_GENERATION)

            await self.emit(EventType.AGENT_PROGRESS, "📋 Parsing test suites and run instructions...", progress=0.85)
            findings = self._parse_findings(result)

            for f in findings:
                await self.emit(
                    EventType.AGENT_PROGRESS,
                    f"✅ Generated: {f.title}",
                    progress=0.9,
                    findings_count=len(findings),
                )
        except Exception as e:
            await self.emit(EventType.AGENT_PROGRESS, f"❌ Error: {str(e)}", progress=1.0)
            findings = []

        await self.emit(
            EventType.AGENT_DONE,
            f"✅ Test generation complete — {len(findings)} test suites created",
            progress=1.0,
            findings_count=len(findings),
        )
        return findings

    def _build_file_content(self, files: dict[str, str]) -> str:
        parts = []
        for path, content in files.items():
            numbered = "\n".join(f"{i+1}: {line}" for i, line in enumerate(content.split("\n")[:200]))
            parts.append(f"--- {path} ---\n{numbered}\n")
        return "\n".join(parts)

    def _parse_findings(self, result: dict) -> list[Finding]:
        findings = []
        for f in result.get("findings", []):
            patch = None
            test_code = f.get("test_code", "")
            test_file = f.get("test_file_name", "")
            if test_code:
                patch = Patch(
                    file_path=test_file or f.get("file_path", "test.py"),
                    diff=test_code,
                    description=f"Generated test: {f.get('title', '')}",
                )

            fp = f.get("file_path", "")
            file_path = ", ".join(fp) if isinstance(fp, list) else str(fp)

            test_instr = None
            ti = f.get("test_instructions", {})
            if ti:
                test_instr = TestRunInstructions(
                    framework=ti.get("framework", ""),
                    install_command=ti.get("install_command", ""),
                    run_command=ti.get("run_command", ""),
                    notes=ti.get("notes", ""),
                )

            findings.append(Finding(
                id=self._make_finding_id(),
                agent=self.AGENT_NAME,
                severity=Severity(f.get("severity", "info")),
                confidence=self._normalize_confidence(f.get("confidence", 0.7)),
                title=f.get("title", "Test Suite"),
                description=f.get("recommendation", ""),
                file_path=file_path,
                line_range=f.get("line_range"),
                evidence=f.get("evidence", ""),
                recommendation=f.get("recommendation", ""),
                patch=patch,
                explain_steps=f.get("explain_steps", []),
                test_instructions=test_instr,
            ))
        return findings
