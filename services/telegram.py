from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

import requests

from services.env import env_list, env_value
from services.local_store import get_param


DEFAULT_API_URL = "https://api.telegram.org"


@dataclass(frozen=True)
class TelegramConfig:
    enabled: bool
    token: str
    api_url: str
    allowed_chat_ids: set[str]
    allow_all_chats: bool


def _yes(value: str, default: bool = False) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return default
    return normalized in {"1", "yes", "si", "true", "on"}


def normalize_api_url(value: str) -> str:
    candidate = (value.strip() or DEFAULT_API_URL).rstrip("/")
    marker = "/bot"
    marker_index = candidate.find(marker)
    if marker_index >= 0:
        candidate = candidate[:marker_index]
    parsed = urlsplit(candidate)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
    return candidate


def get_telegram_config() -> TelegramConfig:
    env_token = env_value("TELEGRAM_BOT_TOKEN")
    env_allowed = env_list("TELEGRAM_ALLOWED_CHAT_IDS")
    token = get_param("telegram_bot_token", env_token).strip()
    allowed_text = get_param("telegram_allowed_chat_ids", ",".join(sorted(env_allowed)))
    allowed = {item.strip() for item in allowed_text.split(",") if item.strip()}

    return TelegramConfig(
        enabled=_yes(get_param("telegram_enabled", "yes" if token else "no")),
        token=token,
        api_url=normalize_api_url(
            get_param("telegram_api_url", env_value("TELEGRAM_API_URL", DEFAULT_API_URL))
        ),
        allowed_chat_ids=allowed,
        allow_all_chats=_yes(
            get_param("telegram_allow_all_chats", "yes" if not env_allowed else "no")
        ),
    )


def telegram_request(
    config: TelegramConfig,
    method: str,
    payload: dict | None = None,
    timeout: int = 35,
) -> dict:
    if not config.token:
        raise ValueError("El token de Telegram no esta configurado.")
    url = f"{config.api_url}/bot{config.token}/{method}"
    response = requests.post(url, json=payload or {}, timeout=timeout)
    if not response.ok:
        try:
            description = response.json().get("description", "")
        except ValueError:
            description = ""
        detail = f": {description}" if description else ""
        raise RuntimeError(f"Telegram devolvio HTTP {response.status_code} en {method}{detail}")
    data = response.json()
    if not data.get("ok", False):
        raise RuntimeError(data.get("description") or f"Telegram rechazo la operacion {method}.")
    return data


def test_telegram_connection(token: str, api_url: str) -> tuple[bool, str]:
    config = TelegramConfig(
        enabled=True,
        token=token.strip(),
        api_url=normalize_api_url(api_url),
        allowed_chat_ids=set(),
        allow_all_chats=False,
    )
    try:
        result = telegram_request(config, "getMe", timeout=15).get("result", {})
        username = result.get("username") or "sin_usuario"
        return True, f"Conexion correcta con @{username}."
    except Exception as exc:
        return False, str(exc)


def download_telegram_file(
    config: TelegramConfig,
    file_id: str,
    target_path,
    max_bytes: int,
) -> str:
    file_result = telegram_request(
        config,
        "getFile",
        {"file_id": file_id},
        timeout=20,
    ).get("result", {})
    file_path = str(file_result.get("file_path", "")).strip()
    if not file_path:
        raise RuntimeError("Telegram no devolvio la ruta del archivo.")
    declared_size = int(file_result.get("file_size") or 0)
    if declared_size > max_bytes:
        raise ValueError("El audio supera el limite permitido de 20 MB.")

    url = f"{config.api_url}/file/bot{config.token}/{file_path}"
    total = 0
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        with open(target_path, "wb") as target:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("El audio supera el limite permitido de 20 MB.")
                target.write(chunk)
    return file_path
