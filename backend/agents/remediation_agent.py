"""
RemediationAgent — Autonomous code-fix engine.
Takes validated findings from the critic and generates PRODUCTION-READY fixes:
- Rewrites raw SQL to parameterized queries
- Replaces MD5/SHA1 with bcrypt/argon2
- Adds rate-limit eviction logic
- Fixes prompt injection vulnerabilities
- Replaces insecure patterns with secure alternatives
- Generates complete before/after code with imports and dependencies

This is what elevates the system from "Code Auditor" to "Remediation Engineer."
"""

from __future__ import annotations

import logging
from backend.agents.base_agent import BaseAgent
from backend.core.llm import TaskType
from backend.schemas import (
    AutoFixResult,
    EventType,
    Finding,
    Severity,
)

logger = logging.getLogger(__name__)

REMEDIATION_SYSTEM_PROMPT = """You are a senior remediation engineer. Your ONLY job is to generate PRODUCTION-READY code fixes for security and quality findings.

You are NOT an auditor. The auditing is already done. You receive validated findings with evidence.
Your job is to WRITE THE FIX — complete, runnable, production-ready code.

For each finding, generate a complete auto-fix that includes:

1. **original_code**: The exact vulnerable/problematic code block (copy from evidence)
2. **fixed_code**: The complete rewritten code that fixes the issue. This must be:
   - Drop-in replacement for the original code
   - Production-ready (not pseudo-code)
   - Include all necessary imports at the top
   - Handle edge cases
   - Follow the project's existing code style
3. **fix_type**: Classification of the fix. Use one of:
   - "parameterized_query" — Raw SQL → parameterized/prepared statements
   - "bcrypt_upgrade" — MD5/SHA1/SHA256 password hashing → bcrypt/argon2
   - "orm_migration" — Raw SQL → ORM (SQLAlchemy, Django ORM, etc.)
   - "input_sanitization" — Missing input validation → sanitized inputs
   - "csrf_protection" — Missing CSRF → token-based protection
   - "rate_limit_fix" — Missing/broken rate limiting → proper implementation with eviction
   - "prompt_injection_fix" — Prompt injection vulnerability → sanitized prompts with guardrails
   - "auth_fix" — Authentication bypass → proper auth checks
   - "secret_management" — Hardcoded secrets → environment variables/vault
   - "xss_prevention" — XSS vulnerability → output encoding/CSP
   - "deserialization_fix" — Insecure deserialization → safe parsing
   - "path_traversal_fix" — Directory traversal → path validation
   - "command_injection_fix" — Shell injection → subprocess with args list
   - "dependency_upgrade" — Vulnerable dependency → patched version
   - "general_fix" — Other fixes
4. **explanation**: Why this fix is correct and secure (2-3 sentences)
5. **breaking_changes**: List any breaking changes (empty list if none)
6. **imports_needed**: List of import statements needed (e.g. ["import bcrypt", "from flask_wtf.csrf import CSRFProtect"])
7. **dependencies_needed**: List of pip/npm packages to install (e.g. ["bcrypt", "flask-wtf"])
8. **confidence**: 0.0-1.0 how confident you are this fix is correct
9. **is_safe_to_auto_apply**: true if the fix is trivially safe (e.g. adding an import, fixing a typo), false if it changes logic

FIX PATTERNS — follow these precisely:

### SQL Injection → Parameterized Queries
BEFORE: cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
AFTER:  cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))

### MD5 → bcrypt
BEFORE: hashlib.md5(password.encode()).hexdigest()
AFTER:  bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
VERIFY: bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))

### Rate Limiting with Eviction
BEFORE: rate_limits = {} (no cleanup)
AFTER:  Use TTLCache or manual eviction with timestamps, max entries, and cleanup thread

### Prompt Injection
BEFORE: prompt = f"Analyze: {user_input}"
AFTER:  Sanitize user_input, add system guardrails, use structured output

### Hardcoded Secrets
BEFORE: API_KEY = "sk-abc123..."
AFTER:  API_KEY = os.environ.get("API_KEY") with validation

Return ONLY valid JSON:
{
  "auto_fixes": [
    {
      "finding_id": "security_abc12345",
      "file_path": "app.py",
      "original_code": "cursor.execute(f\\"SELECT * FROM users WHERE id = {user_id}\\")",
      "fixed_code": "cursor.execute(\\"SELECT * FROM users WHERE id = %s\\", (user_id,))",
      "fix_type": "parameterized_query",
      "explanation": "Replaces string interpolation with parameterized query to prevent SQL injection. The %s placeholder is handled by the database driver, which properly escapes the input.",
      "breaking_changes": [],
      "imports_needed": [],
      "dependencies_needed": [],
      "confidence": 0.95,
      "is_safe_to_auto_apply": true
    }
  ],
  "remediation_summary": "Generated 5 production-ready fixes: 2 SQL injection patches, 1 bcrypt upgrade, 1 rate-limit fix, 1 secret management improvement.",
  "unfixable_findings": ["finding_id_1"],
  "unfixable_reasons": {"finding_id_1": "Requires architectural redesign beyond single-file fix"}
}

RULES:
- Only generate fixes for findings with clear, actionable evidence
- fixed_code must be COMPLETE and RUNNABLE — no "..." or "TODO" placeholders
- Include ALL necessary imports in the fixed_code
- If a finding cannot be auto-fixed (needs architectural change), add to unfixable_findings
- Max 15 auto-fixes per batch"""


class RemediationAgent(BaseAgent):
    """
    Autonomous remediation engine — generates production-ready code fixes.
    Takes validated findings and produces apply-ready patches.
    """

    AGENT_NAME = "remediation"

    async def analyze(self, files: dict[str, str], manifest_summary: str) -> list[Finding]:
        """Not used directly — RemediationAgent uses remediate() instead."""
        return []

    async def remediate(
        self,
        findings: list[Finding],
        file_contents: dict[str, str],
        manifest_summary: str,
    ) -> tuple[list[Finding], str]:
        """
        Generate production-ready fixes for validated findings.

        Returns:
            (findings_with_auto_fixes, remediation_summary)
        """
        # Filter to fixable findings (security, performance, prompt quality issues)
        fixable_findings = [
            f for f in findings
            if f.severity in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM)
            and f.agent in ("security", "algorithmic_opt", "prompt_quality", "tests")
            and f.evidence  # Must have evidence to fix
        ]

        if not fixable_findings:
            return findings, "No findings eligible for auto-remediation."

        await self.emit(
            EventType.AGENT_STARTED,
            f"🔧 Remediation engine starting — {len(fixable_findings)} findings to fix",
        )

        # Build the prompt
        findings_text = self._serialize_findings_for_fix(fixable_findings)
        code_context = self._build_code_context(file_contents)

        user_prompt = (
            f"## Findings to fix ({len(fixable_findings)} total):\n\n"
            f"{findings_text}\n\n"
            f"## Source code context:\n\n"
            f"{code_context}\n\n"
            f"## Repo structure:\n{manifest_summary}\n\n"
            f"Generate production-ready fixes for each finding. "
            f"Write COMPLETE, RUNNABLE code — not pseudo-code."
        )

        await self.emit(
            EventType.AGENT_PROGRESS,
            "🧠 Generating production-ready fixes via Mistral...",
            progress=0.3,
        )

        try:
            result = await self.llm.generate_json(
                REMEDIATION_SYSTEM_PROMPT, user_prompt,
                task_type=TaskType.REMEDIATION,
            )

            # Safety: if LLM returned a string, try to parse it as JSON
            if isinstance(result, str):
                import json as _json
                try:
                    result = _json.loads(result)
                except (ValueError, TypeError):
                    logger.warning("RemediationAgent LLM returned unparseable string")
                    result = {"auto_fixes": [], "remediation_summary": "LLM returned invalid format."}

            # Safety: ensure result is a dict
            if not isinstance(result, dict):
                result = {"auto_fixes": [], "remediation_summary": "LLM returned unexpected format."}

            await self.emit(
                EventType.AGENT_PROGRESS,
                "📋 Applying auto-fixes to findings...",
                progress=0.8,
            )

            updated_findings, summary = self._apply_fixes(findings, result)

            # Emit per-fix results
            fix_count = sum(1 for f in updated_findings if f.auto_fix)
            for f in updated_findings:
                if f.auto_fix:
                    await self.emit(
                        EventType.AGENT_PROGRESS,
                        f"✅ Auto-fix: {f.auto_fix.fix_type} for {f.title} in {f.file_path}",
                        progress=0.9,
                        findings_count=fix_count,
                    )

        except Exception as e:
            logger.error(f"RemediationAgent failed: {e}")
            await self.emit(
                EventType.AGENT_PROGRESS,
                f"❌ Remediation error: {e}. Findings passed through without fixes.",
                progress=1.0,
            )
            return findings, f"Remediation failed: {e}. Findings passed through."

        await self.emit(
            EventType.AGENT_DONE,
            f"✅ Remediation complete — {fix_count} production-ready fixes generated",
            progress=1.0,
            findings_count=fix_count,
        )

        return updated_findings, summary

    def _serialize_findings_for_fix(self, findings: list[Finding]) -> str:
        """Convert findings to text optimized for the remediation prompt."""
        parts = []
        for i, f in enumerate(findings, 1):
            parts.append(
                f"### Finding {i} (ID: {f.id})\n"
                f"  Agent: {f.agent}\n"
                f"  Title: {f.title}\n"
                f"  Severity: {f.severity.value}\n"
                f"  File: {f.file_path}\n"
                f"  Lines: {f.line_range}\n"
                f"  Evidence (vulnerable code):\n```\n{f.evidence}\n```\n"
                f"  Recommendation: {f.recommendation}\n"
            )
        return "\n".join(parts)

    def _build_code_context(self, files: dict[str, str]) -> str:
        """Build truncated code context for the remediation engine."""
        parts = []
        for path, content in files.items():
            lines = content.split("\n")[:200]
            numbered = "\n".join(f"{i+1}: {line}" for i, line in enumerate(lines))
            parts.append(f"--- {path} ---\n{numbered}\n")
        return "\n".join(parts)

    def _apply_fixes(
        self, original_findings: list[Finding], result: dict
    ) -> tuple[list[Finding], str]:
        """Apply auto-fix results back to findings."""
        findings_map = {f.id: f for f in original_findings}
        auto_fixes = result.get("auto_fixes", [])

        # Map fixes by finding ID
        fix_map: dict[str, dict] = {}
        for fix in auto_fixes:
            fid = fix.get("finding_id", "")
            if fid:
                fix_map[fid] = fix

        # Apply fixes to findings
        updated: list[Finding] = []
        fix_count = 0
        for finding in original_findings:
            if finding.id in fix_map:
                fix_data = fix_map[finding.id]
                auto_fix = AutoFixResult(
                    finding_id=finding.id,
                    file_path=fix_data.get("file_path", finding.file_path),
                    original_code=fix_data.get("original_code", ""),
                    fixed_code=fix_data.get("fixed_code", ""),
                    fix_type=fix_data.get("fix_type", "general_fix"),
                    explanation=fix_data.get("explanation", ""),
                    breaking_changes=fix_data.get("breaking_changes", []),
                    imports_needed=fix_data.get("imports_needed", []),
                    dependencies_needed=fix_data.get("dependencies_needed", []),
                    confidence=max(0.0, min(1.0, float(fix_data.get("confidence", 0.8)))),
                    is_safe_to_auto_apply=fix_data.get("is_safe_to_auto_apply", False),
                )
                finding = finding.model_copy(update={"auto_fix": auto_fix})
                fix_count += 1
                logger.info(f"Applied auto-fix ({auto_fix.fix_type}) to finding {finding.id}")

            updated.append(finding)

        summary = result.get(
            "remediation_summary",
            f"Generated {fix_count} production-ready fixes out of {len(original_findings)} findings.",
        )

        unfixable = result.get("unfixable_findings", [])
        if unfixable:
            reasons = result.get("unfixable_reasons", {})
            summary += f"\n{len(unfixable)} findings could not be auto-fixed: "
            summary += "; ".join(
                f"{fid}: {reasons.get(fid, 'unknown reason')}"
                for fid in unfixable[:5]
            )

        return updated, summary
