from __future__ import annotations

import os
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR / "data"
LOGS_DIR = APP_DIR / "logs"
EXPORTS_DIR = DATA_DIR / "exports"
MARIA_UPLOADS_DIR = DATA_DIR / "maria_uploads"


def ensure_dirs() -> None:
    for path in (DATA_DIR, LOGS_DIR, EXPORTS_DIR, MARIA_UPLOADS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def ensure_app_dirs() -> None:
    ensure_dirs()


def sqlite_path() -> Path:
    return Path(os.getenv("WALLY_AGENT_SQLITE_PATH", str(DATA_DIR / "wally_agent.sqlite")))
