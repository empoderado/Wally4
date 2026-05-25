from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import requests

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from orchestration.maria_orchestrator import answer
from services.env import env_list, env_value
from services.local_store import init_store
from services.paths import LOGS_DIR, ensure_dirs


def configure_logging() -> None:
    ensure_dirs()
    logging.basicConfig(
        filename=LOGS_DIR / "maria_telegram.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def telegram_request(token: str, method: str, payload: dict | None = None, timeout: int = 35) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    response = requests.post(url, json=payload or {}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def send_message(token: str, chat_id: int | str, text: str) -> None:
    telegram_request(
        token,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        },
        timeout=20,
    )


def is_allowed(chat_id: int | str, allowed_chat_ids: set[str]) -> bool:
    if not allowed_chat_ids:
        return True
    return str(chat_id) in allowed_chat_ids


def handle_message(token: str, message: dict, allowed_chat_ids: set[str]) -> None:
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    if chat_id is None:
        return

    if not is_allowed(chat_id, allowed_chat_ids):
        send_message(token, chat_id, "No tienes autorizacion para consultar Mar-IA Agent.")
        logging.warning("Chat no autorizado: %s", chat_id)
        return

    text = (message.get("text") or "").strip()
    user = message.get("from", {})
    user_name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")])).strip()
    user_id = str(user.get("id") or chat_id)

    if not text:
        send_message(token, chat_id, "Por ahora puedo responder mensajes de texto. La lectura de audio e imagen queda para la siguiente capa.")
        return

    if text.lower() in {"/start", "hola", "inicio"}:
        send_message(
            token,
            chat_id,
            "Hola, soy Mar-IA Agent. Puedes preguntarme por ventas, inventario, embarques, vendedores y referencias de Wally.",
        )
        return

    response = answer(text, channel="telegram", user_id=user_id, user_name=user_name)
    send_message(token, chat_id, response)


def main() -> None:
    configure_logging()
    init_store()
    token = env_value("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Configure TELEGRAM_BOT_TOKEN en C:\\Apps\\WallyAgent\\.env")

    allowed_chat_ids = env_list("TELEGRAM_ALLOWED_CHAT_IDS")
    logging.info("Mar-IA Telegram iniciado. Chats permitidos: %s", ",".join(sorted(allowed_chat_ids)) or "todos")
    print("Mar-IA Telegram iniciado.")

    offset = None
    while True:
        try:
            payload = {"timeout": 30}
            if offset is not None:
                payload["offset"] = offset
            data = telegram_request(token, "getUpdates", payload, timeout=40)
            for update in data.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message") or update.get("edited_message")
                if message:
                    handle_message(token, message, allowed_chat_ids)
        except requests.HTTPError as exc:
            logging.exception("Error HTTP en Telegram: %s", exc)
            print(f"Error temporal consultando Telegram: {exc}. Reintentando en 10 segundos...")
            time.sleep(10)
        except Exception as exc:
            logging.exception("Error en Mar-IA Telegram: %s", exc)
            print(f"Error temporal en Mar-IA Telegram: {exc}. Reintentando en 10 segundos...")
            time.sleep(10)


if __name__ == "__main__":
    main()
