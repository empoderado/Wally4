from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

from services.paths import APP_DIR


@lru_cache(maxsize=1)
def load_app_env() -> None:
    env_path = APP_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def env_value(key: str, default: str = "") -> str:
    load_app_env()
    return os.getenv(key, default).strip()


def env_list(key: str) -> set[str]:
    value = env_value(key)
    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}
