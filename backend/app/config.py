"""Environment-backed configuration for CloudOps AI."""
from __future__ import annotations

import os


def database_path() -> str:
    return os.getenv("CLOUDOPS_DB_PATH", "./data/cloudops.db")


def correlation_window_seconds() -> int:
    raw = os.getenv("CLOUDOPS_CORRELATION_WINDOW_SECONDS", "300")
    try:
        return max(1, min(int(raw), 86_400))
    except ValueError:
        return 300


def cors_origins() -> list[str]:
    raw = os.getenv("CLOUDOPS_CORS_ORIGINS", "http://localhost:3000")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]
