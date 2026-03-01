"""
AlgorithmicOptimizationAgent — Deep algorithmic complexity analysis.
Focuses on time/space complexity, data structure redesign, memoization,
caching strategies, and structural performance optimization.
"""

from __future__ import annotations

import asyncio

from backend.agents.base_agent import BaseAgent
from backend.schemas import (
    EventType, Finding, Patch, Severity,
    BenchmarkGuidance,
)

SYSTEM_PROMPT = """You are a senior algorithm engineer and performance optimization specialist.

Your task is to analyze the provided codebase strictly from an algorithmic and computational complexity perspective.

Focus ONLY on algorithmic inefficiencies and structural performance problems.
Do NOT suggest minor micro-optimizations unless they have measurable impact.

For each issue you identify, follow this reasoning order:

1. Identify the exact code location (file path and line numbers).
2. Explain the algorithmic pattern currently used.
3. Explicitly compute the current time complexity using Big-O notation.
4. If relevant, compute space complexity.
5. Propose a structurally improved approach.
6. Compute the improved time complexity using Big-O notation.
7. Mention trade-offs (memory vs speed, readability vs performance).
8. Provide measurable benchmarking guidance (tool, command, expected impact).
9. Assign severity based on real-world impact.
10. Assign confidence (0.0–1.0) using this scale:
    0.9–1.0 → Clear algorithmic inefficiency with strong evidence
    0.7–0.8 → Strong inefficiency but contextual assumptions exist
    0.5–0.6 → Possible inefficiency but not certain
    Below 0.5 → Do NOT include

Strict Rules:
- Only report findings backed by explicit code evidence
- Do NOT fabricate inefficiencies
- Do NOT optimize prematurely
- If no meaningful algorithmic inefficiencies exist, return an empty findings list
- Prefer algorithmic restructuring (data structures, indexing, memoization, caching strategy redesign)
- Avoid trivial suggestions like "use faster variable names" or "remove print statements"

Areas of focus:
- Nested iteration creating O(n²) or worse — propose hash-map indexing, sorting + two-pointer, etc.
- Repeated expensive computation inside loops — propose memoization or precomputation
- Linear search where O(1) lookup is possible — propose dict/set/hashmap
- Unbounded recursion — propose iterative + stack or tail-call optimization
- Redundant data traversal — propose single-pass algorithms
- Missing caching for repeated I/O or computation
- Suboptimal data structure choice (list vs set, array vs deque, etc.)
- N+1 query patterns in ORM/database code

Return ONLY valid JSON:
{
  "findings": [
    {
      "title": "Short title of algorithmic issue",
      "severity": "critical|high|medium|low|info",
      "confidence": 0.85,
      "file_path": "relative/path/to/file",
      "line_range": [start, end],
      "why_slow": "Algorithmic explanation: what pattern is used, WHY it is slow. Example: 'Lines 42-55: Nested for-loops iterate users[] × orders[] doing linear membership check per pair, creating O(n×m) comparisons on every API request. With 10K users and 50K orders this is 500M iterations.'",
      "what_to_change": "Structural fix: Example: 'Pre-build a set of order user_ids before the outer loop. Replace inner linear scan with O(1) set lookup. Alternatively, use a dict keyed by user_id mapping to order lists.'",
      "complexity_delta": "O(n×m) → O(n+m)",
      "space_tradeoff": "Extra O(m) memory for the lookup set — negligible for typical dataset sizes",
      "minimal_patch": "Minimal code patch showing the algorithmic fix (unified diff or code snippet)",
      "how_to_benchmark": {
        "tool": "pytest-benchmark | timeit | cProfile | time.perf_counter",
        "command": "python -m timeit -s 'from module import func' 'func(test_data)'",
        "expected_improvement": "~100x for n>1000, ~10000x for n>10000",
        "before_complexity": "O(n²)",
        "after_complexity": "O(n)"
      },
      "evidence": "The exact slow code snippet with line numbers",
      "explain_steps": [
        "Identified nested loop over users and orders at lines 42-55",
        "Current pattern: for each user, linear scan all orders → O(n×m)",
        "Proposed: pre-index orders by user_id into dict → O(n+m)",
        "Trade-off: O(m) extra memory, negligible for typical datasets",
        "Benchmarked with timeit: 500ms → 2ms for 10K×50K dataset"
      ]
    }
  ]
}

Be EVIDENCE-BASED. Cite specific line numbers, variable names, and data structures.
Max 8 findings. Prioritize by real-world impact × confidence.
If the codebase has no meaningful algorithmic issues, return {"findings": []}."""


class AlgorithmicOptimizationAgent(BaseAgent):
    AGENT_NAME = "algorithmic_opt"

    async def analyze(self, files: dict[str, str], manifest_summary: str) -> list[Finding]:
        total = len(files)
        await self.emit(EventType.AGENT_STARTED, f"🔬 Starting algorithmic complexity analysis — {total} files")

        # ── Progressive complexity profiling ────────────────────
        hotspots = []
        scanned = 0
        total_loops = 0
        recursive_files = []

        for path, content in files.items():
            scanned += 1
            lines = content.split("\n")
            line_count = len(lines)
            lower = content.lower()

            # Detect algorithmic patterns
            loop_count = lower.count("for ") + lower.count("while ")
            total_loops += loop_count
            has_nested = loop_count >= 2

            # Detect recursion
            # Simple heuristic: function calls itself
            if "def " in content:
                func_names = [l.split("def ")[1].split("(")[0].strip()
                              for l in content.split("\n")
                              if "def " in l and "(" in l]
                for fn in func_names:
                    if fn and content.count(fn) > 1:
                        recursive_files.append((path, fn))

            # Detect data structure concerns
            has_linear_search = any(k in lower for k in [
                "in list", ".index(", "for .* in .*if",
                ".count(", "enumerate"
            ])
            has_io_in_loop = any(k in lower for k in [
                "open(", ".read(", ".write(", "requests.",
                "fetch(", ".query(", ".execute(", "session.get",
            ])

            if has_nested or loop_count > 4:
                hotspots.append((path, loop_count, line_count))
                await self.emit(
                    EventType.AGENT_PROGRESS,
                    f"🔥 Complexity hotspot: {path} — {loop_count} loop constructs, {line_count} lines",
                    progress=round(scanned / total * 0.2, 2),
                )

            if has_io_in_loop and loop_count > 0:
                await self.emit(
                    EventType.AGENT_PROGRESS,
                    f"⚠️ I/O inside loop: {path} — potential N+1 or unbatched operations",
                    progress=round(scanned / total * 0.2, 2),
                )

            if scanned % max(1, total // 3) == 0:
                await self.emit(
                    EventType.AGENT_PROGRESS,
                    f"Profiling {scanned}/{total}: {path}",
                    progress=round(scanned / total * 0.2, 2),
                )
                await asyncio.sleep(0)

        # Summary reports
        if hotspots:
            hotspots.sort(key=lambda x: x[1], reverse=True)
            top = ", ".join(f"{p} ({n} loops)" for p, n, _ in hotspots[:3])
            await self.emit(
                EventType.AGENT_PROGRESS,
                f"📊 {len(hotspots)} hotspots found — Top: {top}",
                progress=0.25,
            )

        if recursive_files:
            rec_list = ", ".join(f"{p}:{fn}()" for p, fn in recursive_files[:3])
            await self.emit(
                EventType.AGENT_PROGRESS,
                f"🔄 Recursive patterns: {rec_list}",
                progress=0.28,
            )

        await self.emit(
            EventType.AGENT_PROGRESS,
            f"📈 Total loop constructs: {total_loops} across {total} files",
            progress=0.3,
        )

        # ── LLM deep analysis ─────────────────────────────────
        await self.emit(EventType.AGENT_PROGRESS, "🧠 Analyzing algorithmic complexity via Mistral...", progress=0.4)

        file_content = self._build_file_content(files)
        user_prompt = f"""Repo structure:\n{manifest_summary}\n\nCode files:\n{file_content}"""

        try:
            from backend.core.llm import TaskType
            result = await self.llm.generate_json(SYSTEM_PROMPT, user_prompt, task_type=TaskType.CODE_ANALYSIS)

            await self.emit(EventType.AGENT_PROGRESS, "📋 Computing complexity deltas and generating patches...", progress=0.85)
            findings = self._parse_findings(result)

            for f in findings:
                delta = f.complexity_delta if f.complexity_delta else ""
                await self.emit(
                    EventType.AGENT_PROGRESS,
                    f"🔬 Found: {f.title} {delta} in {f.file_path}",
                    progress=0.9,
                    findings_count=len(findings),
                )
        except Exception as e:
            await self.emit(EventType.AGENT_PROGRESS, f"❌ Error: {str(e)}", progress=1.0)
            findings = []

        await self.emit(
            EventType.AGENT_DONE,
            f"✅ Algorithmic analysis complete — {len(findings)} optimizations found",
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
            # Skip low-confidence findings
            conf = self._normalize_confidence(f.get("confidence", 0.7))
            if conf < 0.5:
                continue

            fp = f.get("file_path", "")
            file_path = ", ".join(fp) if isinstance(fp, list) else str(fp)

            patch = None
            if f.get("minimal_patch"):
                patch = Patch(
                    file_path=file_path,
                    diff=f["minimal_patch"],
                    description=f.get("title", ""),
                )

            benchmark = None
            bm = f.get("how_to_benchmark", {})
            if bm:
                benchmark = BenchmarkGuidance(
                    tool=bm.get("tool", ""),
                    command=bm.get("command", ""),
                    expected_improvement=bm.get("expected_improvement", ""),
                    before_complexity=bm.get("before_complexity", ""),
                    after_complexity=bm.get("after_complexity", ""),
                )

            # Build rich description including space tradeoff
            desc = f.get("what_to_change", "")
            space_tradeoff = f.get("space_tradeoff", "")
            if space_tradeoff:
                desc += f"\n\nSpace trade-off: {space_tradeoff}"

            findings.append(Finding(
                id=self._make_finding_id(),
                agent=self.AGENT_NAME,
                severity=Severity(f.get("severity", "medium")),
                confidence=conf,
                title=f.get("title", "Algorithmic Optimization"),
                description=desc,
                file_path=file_path,
                line_range=f.get("line_range"),
                evidence=f.get("evidence", ""),
                recommendation=f.get("what_to_change", ""),
                patch=patch,
                explain_steps=f.get("explain_steps", []),
                why_slow=f.get("why_slow", ""),
                complexity_delta=f.get("complexity_delta", ""),
                benchmark=benchmark,
            ))
        return findings
