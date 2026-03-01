"""
SecurityAgent — OWASP-style security analysis with defensive remediation.
Includes guardrails: focuses on remediation, avoids exploit-building.
"""

from __future__ import annotations

import asyncio

from backend.agents.base_agent import BaseAgent
from backend.schemas import EventType, Finding, Patch, Severity

SYSTEM_PROMPT = """You are a senior application security engineer performing OWASP-style defensive code review.

GUARDRAILS:
- Focus ONLY on defensive remediation guidance
- Do NOT provide exploit code or attack payloads
- Do NOT demonstrate how to exploit vulnerabilities
- Recommendations must be about FIXING, not attacking

Analyze code for:
- SQL injection / NoSQL injection
- XSS (reflected, stored, DOM-based)
- CSRF / missing CSRF tokens
- Authentication bypass / broken auth
- Hardcoded secrets / API keys in code
- Insecure deserialization
- Path traversal / directory traversal
- Command injection / shell injection
- SSRF (Server-Side Request Forgery)
- Missing input validation / sanitization
- Insecure direct object references (IDOR)
- Missing rate limiting
- Insecure cryptography
- Sensitive data exposure in logs

Return ONLY valid JSON:
{
  "findings": [
    {
      "title": "Short vulnerability title",
      "severity": "critical|high|medium|low|info",
      "confidence": 0.85,
      "description": "What the vulnerability is and its impact",
      "file_path": "relative/path/to/file",
      "line_range": [start_line, end_line],
      "evidence": "The vulnerable code snippet (sanitized, no exploit payloads)",
      "recommendation": "Specific defensive remediation steps",
      "patch_diff": "Unified diff showing the secure fix",
      "explain_steps": [
        "Checked authentication flow in auth.py",
        "Found user input flows directly to SQL query at line 42",
        "Proposed parameterized query to prevent injection"
      ]
    }
  ]
}

Be precise about file paths and line numbers. Max 10 findings.
REMEMBER: You are defending, not attacking."""


class SecurityAgent(BaseAgent):
    AGENT_NAME = "security"

    async def analyze(self, files: dict[str, str], manifest_summary: str) -> list[Finding]:
        total = len(files)
        await self.emit(EventType.AGENT_STARTED, f"🛡️ Starting OWASP security scan — {total} files to analyze")

        # ── Progressive file scanning events ──────────────────
        scanned = 0
        sensitive_hints = []
        for path, content in files.items():
            scanned += 1
            lower = content.lower()

            # Emit progress every few files
            if scanned % max(1, total // 4) == 0 or scanned == total:
                await self.emit(
                    EventType.AGENT_PROGRESS,
                    f"Scanning file {scanned}/{total}: {path}",
                    progress=round(scanned / total * 0.3, 2),
                )
                await asyncio.sleep(0)  # yield for SSE flush

            # Detect sensitive patterns and report
            if any(k in lower for k in ["password", "secret", "api_key", "token", "private_key"]):
                sensitive_hints.append(path)
            if any(k in lower for k in ["execute(", "raw(", "cursor", "eval(", "exec("]):
                await self.emit(
                    EventType.AGENT_PROGRESS,
                    f"⚡ Potential injection risk in {path}",
                    progress=round(scanned / total * 0.3, 2),
                )

        if sensitive_hints:
            await self.emit(
                EventType.AGENT_PROGRESS,
                f"🔑 Found {len(sensitive_hints)} files with credential patterns: {', '.join(sensitive_hints[:3])}",
                progress=0.35,
            )

        # ── LLM analysis ──────────────────────────────────────
        await self.emit(EventType.AGENT_PROGRESS, "🧠 Sending to Mistral for deep vulnerability analysis...", progress=0.4)

        file_content = self._build_file_content(files)
        user_prompt = f"""Repo structure:\n{manifest_summary}\n\nCode files:\n{file_content}"""

        try:
            from backend.core.llm import TaskType
            result = await self.llm.generate_json(SYSTEM_PROMPT, user_prompt, task_type=TaskType.SECURITY_SCAN)

            await self.emit(EventType.AGENT_PROGRESS, "📋 Parsing findings and generating patches...", progress=0.85)
            findings = self._parse_findings(result)

            # Emit per-finding discovery
            for f in findings:
                await self.emit(
                    EventType.AGENT_PROGRESS,
                    f"🔴 Found: {f.title} [{f.severity.value}] in {f.file_path}",
                    progress=0.9,
                    findings_count=len(findings),
                )
        except Exception as e:
            await self.emit(EventType.AGENT_PROGRESS, f"❌ Error: {str(e)}", progress=1.0)
            findings = []

        await self.emit(
            EventType.AGENT_DONE,
            f"✅ Security scan complete — {len(findings)} vulnerabilities found",
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
            fp = f.get("file_path", "")
            file_path = ", ".join(fp) if isinstance(fp, list) else str(fp)

            patch = None
            if f.get("patch_diff"):
                patch = Patch(
                    file_path=file_path,
                    diff=f["patch_diff"],
                    description=f.get("title", ""),
                )
            findings.append(Finding(
                id=self._make_finding_id(),
                agent=self.AGENT_NAME,
                severity=Severity(f.get("severity", "info")),
                confidence=self._normalize_confidence(f.get("confidence", 0.7)),
                title=f.get("title", "Security Finding"),
                description=f.get("description", ""),
                file_path=file_path,
                line_range=f.get("line_range"),
                evidence=f.get("evidence", ""),
                recommendation=f.get("recommendation", ""),
                patch=patch,
                explain_steps=f.get("explain_steps", []),
            ))
        return findings
