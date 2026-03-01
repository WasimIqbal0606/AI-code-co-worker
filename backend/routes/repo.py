"""
Repo routes: upload zip, get manifest.
"""

from __future__ import annotations

import os
import shutil
import uuid
import zipfile
import tempfile

from fastapi import APIRouter, UploadFile, File, HTTPException

from backend.core.store import store
from backend.core.file_utils import build_manifest
from backend.schemas import RepoManifest

router = APIRouter(prefix="/repo", tags=["repo"])

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")


@router.post("/upload", response_model=RepoManifest)
async def upload_repo(file: UploadFile = File(...)):
    """Accept a zip file, unzip to workspace, build manifest."""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files accepted")

    repo_id = uuid.uuid4().hex[:12]
    workspace = os.path.join(UPLOAD_DIR, repo_id)
    os.makedirs(workspace, exist_ok=True)

    # Save uploaded zip to temp file
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    try:
        content = await file.read()
        tmp.write(content)
        tmp.close()

        # Extract
        with zipfile.ZipFile(tmp.name, "r") as zf:
            zf.extractall(workspace)

        # If zip contains a single top-level folder, use it as root
        entries = os.listdir(workspace)
        if len(entries) == 1 and os.path.isdir(os.path.join(workspace, entries[0])):
            workspace = os.path.join(workspace, entries[0])

    except zipfile.BadZipFile:
        shutil.rmtree(workspace, ignore_errors=True)
        raise HTTPException(status_code=400, detail="Invalid zip file")
    finally:
        os.unlink(tmp.name)

    # Build manifest
    manifest = build_manifest(repo_id, workspace)
    await store.save_repo(manifest, workspace)

    return manifest


@router.get("/{repo_id}/manifest", response_model=RepoManifest)
async def get_manifest(repo_id: str):
    """Return the repo manifest."""
    manifest = await store.get_repo(repo_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Repo not found")
    return manifest
