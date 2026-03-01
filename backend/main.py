"""
FastAPI application entry point.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load env vars from .env file in project root
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from backend.routes import repo, run  # noqa: E402
from backend.core.store import store   # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Restore persisted repos from disk before serving any requests."""
    store.restore_from_disk()
    yield

app = FastAPI(
    title="AI Code Co-Worker",
    description="Claude-like AI code analysis with multi-agent orchestration",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS – allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount route modules
app.include_router(repo.router)
app.include_router(run.router)

# Ensure upload directory exists
os.makedirs(os.getenv("UPLOAD_DIR", "./uploads"), exist_ok=True)


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
