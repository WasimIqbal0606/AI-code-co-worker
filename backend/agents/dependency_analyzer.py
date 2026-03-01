"""
DependencyAnalyzer — Parses dependency manifests and produces security/quality findings.
Runs before agent routing to inject dependency context into the analysis pipeline.
Supports: requirements.txt, package.json, pyproject.toml
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Optional

from backend.schemas import Finding, Severity, Patch

logger = logging.getLogger(__name__)

# ── Known risky / deprecated packages ────────────────────────────────

RISKY_PACKAGES = {
    # Python
    "pycrypto": ("Use 'pycryptodome' instead — pycrypto is unmaintained and has known CVEs.", Severity.HIGH),
    "django-debug-toolbar": ("Must be disabled in production — exposes internal state.", Severity.MEDIUM),
    "pickle5": ("Pickle deserialization is inherently unsafe for untrusted data.", Severity.HIGH),
    "pyyaml": ("Ensure yaml.safe_load() is used — yaml.load() allows code execution.", Severity.MEDIUM),
    "httplib2": ("Consider using 'httpx' or 'requests' — httplib2 has limited maintenance.", Severity.LOW),
    "telnetlib": ("Telnet is unencrypted — use SSH instead.", Severity.HIGH),
    "flask-cors": ("Ensure CORS origins are restricted — wildcard '*' is dangerous.", Severity.MEDIUM),
    # JavaScript / Node
    "event-stream": ("Compromised in 2018 supply-chain attack — verify version.", Severity.CRITICAL),
    "ua-parser-js": ("Had supply-chain attack in 2021 — verify version.", Severity.HIGH),
    "colors": ("Sabotaged by maintainer (v1.4.1+) — pin to safe version.", Severity.HIGH),
    "faker": ("Sabotaged by maintainer (v6.6.6) — pin to safe version.", Severity.HIGH),
    "request": ("Deprecated — use 'node-fetch', 'axios', or 'undici'.", Severity.LOW),
    "lodash": ("Check for prototype pollution CVEs if version < 4.17.21.", Severity.MEDIUM),
    "express": ("Verify version ≥ 4.19 for security patches.", Severity.LOW),
}

# ── Outdated framework heuristics ────────────────────────────────────

# (package_name, version_threshold, message)
OUTDATED_RULES: list[tuple[str, str, str, Severity]] = [
    ("django", "3.0", "Django < 3.0 is end-of-life — upgrade to 4.x+.", Severity.HIGH),
    ("flask", "2.0", "Flask < 2.0 lacks async support — consider upgrading.", Severity.LOW),
    ("fastapi", "0.100", "FastAPI < 0.100 has known issues — upgrade recommended.", Severity.LOW),
    ("react", "17.0", "React < 17 misses concurrent features and security patches.", Severity.MEDIUM),
    ("angular", "14.0", "Angular < 14 is out of LTS — upgrade recommended.", Severity.MEDIUM),
    ("vue", "3.0", "Vue 2 reaches end-of-life — migrate to Vue 3.", Severity.MEDIUM),
    ("next", "13.0", "Next.js < 13 misses app router and key security fixes.", Severity.MEDIUM),
    ("numpy", "1.20", "NumPy < 1.20 has known memory safety issues.", Severity.LOW),
    ("tensorflow", "2.10", "TensorFlow < 2.10 has critical CVEs.", Severity.HIGH),
    ("torch", "2.0", "PyTorch < 2.0 misses compile() and security fixes.", Severity.LOW),
    ("requests", "2.28", "Requests < 2.28 has known vulnerabilities.", Severity.MEDIUM),
    ("axios", "1.0", "Axios < 1.0 has prototype pollution risks.", Severity.MEDIUM),
    ("express", "4.18", "Express < 4.18 has known security issues.", Severity.MEDIUM),
]

# ── Test frameworks to look for ──────────────────────────────────────

PYTHON_TEST_FRAMEWORKS = {"pytest", "unittest", "nose", "nose2", "tox", "coverage", "pytest-cov"}
JS_TEST_FRAMEWORKS = {"jest", "mocha", "chai", "jasmine", "vitest", "cypress", "playwright", "@testing-library/react"}


class DependencyAnalyzer:
    """
    Parses dependency manifests from uploaded repo files.
    Produces findings for risky/outdated deps and missing test frameworks.
    """

    def __init__(self):
        self.dependencies: dict[str, dict] = {}   # name → {version, source_file}
        self.dev_dependencies: dict[str, dict] = {}
        self.findings: list[Finding] = []
        self.dep_summary_lines: list[str] = []
        self._finding_counter = 0

    def analyze(self, file_contents: dict[str, str]) -> tuple[list[Finding], str]:
        """
        Analyze all dependency files found in repository.
        Returns (findings, dependency_context_summary).
        """
        for path, content in file_contents.items():
            basename = path.rsplit("/", 1)[-1].lower()

            if basename == "requirements.txt":
                self._parse_requirements_txt(path, content)
            elif basename == "package.json":
                self._parse_package_json(path, content)
            elif basename == "pyproject.toml":
                self._parse_pyproject_toml(path, content)

        if not self.dependencies and not self.dev_dependencies:
            return [], "No dependency manifests found."

        # Run checks
        self._check_risky_packages()
        self._check_outdated_frameworks()
        self._check_missing_test_framework()

        # Build context summary for other agents
        summary = self._build_summary()

        return self.findings, summary

    # ── Parsers ──────────────────────────────────────────────────────

    def _parse_requirements_txt(self, path: str, content: str):
        """Parse Python requirements.txt."""
        for line_num, line in enumerate(content.splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue

            # Handle: package==1.0, package>=1.0, package~=1.0, package
            match = re.match(r'^([a-zA-Z0-9_.-]+)\s*([>=<~!]+)?\s*([0-9][0-9a-zA-Z.*]*)?', line)
            if match:
                name = match.group(1).lower().replace("-", "_")
                version = match.group(3) or ""
                self.dependencies[name] = {
                    "version": version,
                    "source": path,
                    "line": line_num,
                    "raw": line,
                }
                self.dep_summary_lines.append(f"  {name}=={version}" if version else f"  {name}")

    def _parse_package_json(self, path: str, content: str):
        """Parse Node.js package.json."""
        try:
            pkg = json.loads(content)
        except json.JSONDecodeError:
            return

        for section, target in [
            ("dependencies", self.dependencies),
            ("devDependencies", self.dev_dependencies),
        ]:
            for name, ver_spec in pkg.get(section, {}).items():
                clean_name = name.lower()
                version = re.sub(r'^[\^~>=<]', '', str(ver_spec))
                target[clean_name] = {
                    "version": version,
                    "source": path,
                    "line": 0,
                    "raw": f'"{name}": "{ver_spec}"',
                }
                self.dep_summary_lines.append(f"  {name}@{ver_spec} ({section})")

    def _parse_pyproject_toml(self, path: str, content: str):
        """Parse pyproject.toml dependencies (basic regex-based)."""
        in_deps = False
        for line_num, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()

            # Detect [project.dependencies] or [tool.poetry.dependencies]
            if re.match(r'^\[(project\.dependencies|tool\.poetry\.dependencies)\]', stripped):
                in_deps = True
                continue
            elif stripped.startswith("[") and in_deps:
                in_deps = False
                continue

            if in_deps:
                # Handle: "package>=1.0" or package = "^1.0"
                match = re.match(r'^"?([a-zA-Z0-9_.-]+)"?\s*[>=<~^]*\s*"?([0-9][0-9a-zA-Z.*]*)?', stripped)
                if not match:
                    # TOML key = value style
                    match = re.match(r'^([a-zA-Z0-9_.-]+)\s*=\s*"?[\^~>=]*([0-9][0-9a-zA-Z.*]*)?', stripped)
                if match:
                    name = match.group(1).lower().replace("-", "_")
                    version = match.group(2) or ""
                    self.dependencies[name] = {
                        "version": version,
                        "source": path,
                        "line": line_num,
                        "raw": stripped,
                    }
                    self.dep_summary_lines.append(f"  {name}=={version}" if version else f"  {name}")

    # ── Checks ───────────────────────────────────────────────────────

    def _check_risky_packages(self):
        """Flag known risky/vulnerable packages."""
        all_deps = {**self.dependencies, **self.dev_dependencies}
        for pkg_name, (reason, severity) in RISKY_PACKAGES.items():
            normalized = pkg_name.lower().replace("-", "_")
            if normalized in all_deps:
                dep = all_deps[normalized]
                self.findings.append(self._make_finding(
                    title=f"Risky dependency: {pkg_name}",
                    description=reason,
                    severity=severity,
                    confidence=0.85,
                    file_path=dep["source"],
                    line_range=[dep["line"], dep["line"]] if dep["line"] else None,
                    evidence=dep["raw"],
                    recommendation=reason,
                ))

    def _check_outdated_frameworks(self):
        """Flag outdated framework versions using heuristic comparison."""
        all_deps = {**self.dependencies, **self.dev_dependencies}
        for pkg_name, threshold, message, severity in OUTDATED_RULES:
            normalized = pkg_name.lower().replace("-", "_")
            if normalized in all_deps:
                dep = all_deps[normalized]
                dep_version = dep["version"]
                if dep_version and self._version_lt(dep_version, threshold):
                    self.findings.append(self._make_finding(
                        title=f"Outdated framework: {pkg_name} {dep_version}",
                        description=f"{message} Current: {dep_version}, recommended minimum: {threshold}",
                        severity=severity,
                        confidence=0.75,
                        file_path=dep["source"],
                        line_range=[dep["line"], dep["line"]] if dep["line"] else None,
                        evidence=dep["raw"],
                        recommendation=message,
                    ))

    def _check_missing_test_framework(self):
        """Flag if no test framework is found in dependencies."""
        all_deps = {**self.dependencies, **self.dev_dependencies}
        dep_names = set(all_deps.keys())

        has_python_tests = bool(dep_names & {n.replace("-", "_") for n in PYTHON_TEST_FRAMEWORKS})
        has_js_tests = bool(dep_names & {n.replace("-", "_").replace("@", "") for n in JS_TEST_FRAMEWORKS})

        # Detect if it's a Python or JS project
        has_python_deps = any(d["source"].endswith(".txt") or d["source"].endswith(".toml") for d in all_deps.values())
        has_js_deps = any(d["source"].endswith(".json") for d in all_deps.values())

        if has_python_deps and not has_python_tests:
            source_files = [d["source"] for d in all_deps.values() if d["source"].endswith((".txt", ".toml"))]
            self.findings.append(self._make_finding(
                title="Missing Python test framework",
                description="No test framework (pytest, unittest, etc.) found in dependencies. Test coverage is likely missing.",
                severity=Severity.MEDIUM,
                confidence=0.80,
                file_path=source_files[0] if source_files else "",
                recommendation="Add 'pytest' to dev dependencies: pip install pytest",
            ))

        if has_js_deps and not has_js_tests:
            source_files = [d["source"] for d in all_deps.values() if d["source"].endswith(".json")]
            self.findings.append(self._make_finding(
                title="Missing JavaScript test framework",
                description="No test framework (jest, vitest, mocha, etc.) found in package.json. Test coverage is likely missing.",
                severity=Severity.MEDIUM,
                confidence=0.80,
                file_path=source_files[0] if source_files else "",
                recommendation="Add a test framework: npm install --save-dev jest",
            ))

    # ── Helpers ──────────────────────────────────────────────────────

    def _make_finding(
        self,
        title: str,
        description: str,
        severity: Severity,
        confidence: float = 0.8,
        file_path: str = "",
        line_range: Optional[list[int]] = None,
        evidence: str = "",
        recommendation: str = "",
    ) -> Finding:
        return Finding(
            id=f"dep_{uuid.uuid4().hex[:8]}",
            agent="dependency",
            severity=severity,
            confidence=confidence,
            title=title,
            description=description,
            file_path=file_path,
            line_range=line_range,
            evidence=evidence,
            recommendation=recommendation,
            explain_steps=[
                f"Parsed dependency file: {file_path}",
                f"Matched against known vulnerability/outdated database",
                f"Severity assigned based on impact assessment",
            ],
        )

    @staticmethod
    def _version_lt(version: str, threshold: str) -> bool:
        """Simple version comparison (major.minor only)."""
        try:
            v_parts = [int(x) for x in re.split(r'[.\-a-zA-Z]', version) if x.isdigit()][:2]
            t_parts = [int(x) for x in re.split(r'[.\-a-zA-Z]', threshold) if x.isdigit()][:2]
            # Pad to 2 elements
            while len(v_parts) < 2:
                v_parts.append(0)
            while len(t_parts) < 2:
                t_parts.append(0)
            return v_parts < t_parts
        except (ValueError, IndexError):
            return False

    def _build_summary(self) -> str:
        """Build a dependency context summary for injection into agent prompts."""
        lines = [
            f"Dependency Analysis: {len(self.dependencies) + len(self.dev_dependencies)} packages found",
            f"  Production: {len(self.dependencies)}",
            f"  Dev: {len(self.dev_dependencies)}",
            f"  Issues found: {len(self.findings)}",
            "",
            "Packages:",
        ]
        lines.extend(self.dep_summary_lines[:50])  # Cap at 50 packages
        if len(self.dep_summary_lines) > 50:
            lines.append(f"  ... and {len(self.dep_summary_lines) - 50} more")
        return "\n".join(lines)
