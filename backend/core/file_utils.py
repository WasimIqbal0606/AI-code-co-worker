"""
File utilities: filtering, size limits, and manifest building.
"""

from __future__ import annotations

import os
from pathlib import Path

from backend.schemas import FileEntry, RepoManifest

# Directories to always skip
IGNORED_DIRS = {
    "node_modules", "venv", ".venv", "env", ".env",
    "dist", "build", ".git", "__pycache__",
    ".next", ".nuxt", ".cache", "coverage",
    ".tox", ".mypy_cache", ".pytest_cache",
}

# Extensions to always skip
IGNORED_EXTENSIONS = {
    ".pyc", ".pyo", ".so", ".dll", ".exe",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
    ".woff", ".woff2", ".ttf", ".eot",
    ".zip", ".tar", ".gz", ".bz2",
    ".lock", ".map",
}

# Limits
MAX_FILES = 200
MAX_FILE_SIZE_BYTES = 100_000   # 100 KB per file
MAX_TOTAL_SIZE_BYTES = 2_000_000  # 2 MB total

# Language mapping
EXT_TO_LANG = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".tsx": "typescript", ".jsx": "javascript",
    ".java": "java", ".go": "go", ".rs": "rust",
    ".rb": "ruby", ".php": "php", ".c": "c", ".cpp": "cpp",
    ".h": "c", ".hpp": "cpp", ".cs": "csharp",
    ".swift": "swift", ".kt": "kotlin",
    ".html": "html", ".css": "css", ".scss": "scss",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml", ".xml": "xml",
    ".md": "markdown", ".txt": "text",
    ".sh": "bash", ".bat": "batch", ".ps1": "powershell",
    ".sql": "sql", ".graphql": "graphql",
    ".dockerfile": "dockerfile", ".tf": "terraform",
}


def _should_skip_dir(name: str) -> bool:
    return name in IGNORED_DIRS or name.startswith(".")


def _should_skip_file(name: str) -> bool:
    _, ext = os.path.splitext(name)
    return ext.lower() in IGNORED_EXTENSIONS


def _detect_language(filename: str) -> str:
    _, ext = os.path.splitext(filename)
    if filename.lower() == "dockerfile":
        return "dockerfile"
    return EXT_TO_LANG.get(ext.lower(), "")


def build_manifest(repo_id: str, root_path: str) -> RepoManifest:
    """
    Walk a repo directory, filter files, and build a RepoManifest.
    Respects max file count and size limits.
    """
    files: list[FileEntry] = []
    total_size = 0

    root = Path(root_path)
    for dirpath, dirnames, filenames in os.walk(root):
        # Filter ignored dirs in-place
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]

        for fname in sorted(filenames):
            if _should_skip_file(fname):
                continue

            full_path = os.path.join(dirpath, fname)
            try:
                size = os.path.getsize(full_path)
            except OSError:
                continue

            if size > MAX_FILE_SIZE_BYTES:
                continue
            if total_size + size > MAX_TOTAL_SIZE_BYTES:
                continue
            if len(files) >= MAX_FILES:
                break

            rel_path = os.path.relpath(full_path, root).replace("\\", "/")
            files.append(FileEntry(
                path=rel_path,
                size_bytes=size,
                language=_detect_language(fname),
            ))
            total_size += size

    return RepoManifest(
        repo_id=repo_id,
        total_files=len(files),
        total_size_bytes=total_size,
        files=files,
    )


def read_file_content(root_path: str, rel_path: str) -> str:
    """Read file content as text, return empty string on failure."""
    try:
        full = os.path.join(root_path, rel_path)
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""
