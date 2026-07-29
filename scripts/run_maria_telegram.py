from __future__ import annotations

import logging
import msvcrt
import sys
import tempfile
import time
from pathlib import Path

import requests

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from orchestration.maria_orchestrator import answer
from services.local_store import init_store
from services.maria_transcription import MAX_AUDIO_BYTES, transcribe_audio
from services.maria_vision import transcribe_image
from services.paths import LOGS_DIR, ensure_dirs
from services.telegram import (
    TelegramConfig,
    download_telegram_file,
    get_telegram_config,
    telegram_request,
)


_INSTANCE_LOCK = None


def configure_logging() -> None:
    ensure_dirs()
    logging.basicConfig(
        filename=LOGS_DIR / "maria_telegram.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def acquire_instance_lock() -> bool:
    global _INSTANCE_LOCK
    lock_path = LOGS_DIR / "maria_telegram.lock"
    handle = open(lock_path, "a+", encoding="ascii")
    if handle.tell() == 0:
        handle.write("1")
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        return False
    _INSTANCE_LOCK = handle
    return True


def send_message(config: TelegramConfig, chat_id: int | str, text: str) -> None:
    chunks = [text[index : index + 4000] for index in range(0, len(text), 4000)] or [""]
    for chunk in chunks:
        telegram_request(
            config,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": chunk,
                "disable_web_page_preview": True,
            },
            timeout=20,
        )


def is_allowed(chat_id: int | str, config: TelegramConfig) -> bool:
    if config.allow_all_chats:
        return True
    return str(chat_id) in config.allowed_chat_ids


def transcribe_telegram_message(config: TelegramConfig, message: dict) -> str | None:
    media = message.get("voice") or message.get("audio")
    if not media:
        return None
    file_id = str(media.get("file_id", "")).strip()
    if not file_id:
        raise ValueError("Telegram no incluyo el identificador del audio.")
    original_name = str(media.get("file_name") or "mensaje_telegram.ogg")
    suffix = Path(original_name).suffix or ".ogg"
    with tempfile.TemporaryDirectory(prefix="maria_telegram_") as temp_dir:
        audio_path = Path(temp_dir) / f"audio{suffix}"
        remote_path = download_telegram_file(
            config,
            file_id,
            audio_path,
            MAX_AUDIO_BYTES,
        )
        if original_name == "mensaje_telegram.ogg":
            original_name = Path(remote_path).name or original_name
        return transcribe_audio(audio_path, original_name)


def process_telegram_image(config: TelegramConfig, message: dict) -> str | None:
    photo = message.get("photo")
    if not photo:
        return None
    photo_item = photo[-1]
    file_id = str(photo_item.get("file_id", "")).strip()
    if not file_id:
        raise ValueError("Telegram no incluyo el identificador de la foto.")

    caption = (message.get("caption") or "").strip()
    with tempfile.TemporaryDirectory(prefix="maria_telegram_") as temp_dir:
        image_path = Path(temp_dir) / "photo.jpg"
        download_telegram_file(
            config,
            file_id,
            image_path,
            10 * 1024 * 1024,
        )
        return transcribe_image(image_path, caption=caption)


def handle_message(config: TelegramConfig, message: dict) -> None:
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    if chat_id is None:
        return

    if not is_allowed(chat_id, config):
        send_message(config, chat_id, "No tienes autorizacion para consultar Mar-IA Agent.")
        logging.warning("Chat no autorizado: %s", chat_id)
        return

    text = (message.get("text") or "").strip()
    user = message.get("from", {})
    user_name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")])).strip()
    user_id = str(user.get("id") or chat_id)

    if not text and (message.get("voice") or message.get("audio")):
        telegram_request(
            config,
            "sendChatAction",
            {"chat_id": chat_id, "action": "typing"},
            timeout=10,
        )
        try:
            text = (transcribe_telegram_message(config, message) or "").strip()
        except Exception as exc:
            logging.exception("No fue posible transcribir audio del chat %s", chat_id)
            send_message(
                config,
                chat_id,
                "No pude transcribir el audio. Revisa la configuracion de transcripcion de Mar-IA o intenta con una nota de voz mas clara.",
            )
            return
        if not text:
            send_message(config, chat_id, "No pude reconocer palabras en el audio.")
            return
        send_message(config, chat_id, f"Entendi: {text}")
    elif not text and message.get("photo"):
        telegram_request(
            config,
            "sendChatAction",
            {"chat_id": chat_id, "action": "typing"},
            timeout=10,
        )
        try:
            text = (process_telegram_image(config, message) or "").strip()
        except Exception as exc:
            logging.exception("No fue posible procesar la imagen del chat %s", chat_id)
            send_message(
                config,
                chat_id,
                "No pude analizar la imagen. Intenta enviando una foto mas clara.",
            )
            return
        if not text:
            send_message(config, chat_id, "No pude extraer informacion o referencias de la imagen.")
            return
        send_message(config, chat_id, f"Entendi de la imagen: {text}")

    if not text:
        send_message(config, chat_id, "Puedo responder mensajes de texto, notas de voz, archivos de audio e imagenes.")
        return

    if text.lower() in {"/start", "hola", "inicio"}:
        send_message(
            config,
            chat_id,
            "Hola, soy Mar-IA Agent. Puedes enviarme texto, una nota de voz o una imagen para consultar ventas, inventario, embarques, vendedores y referencias de Wally.",
        )
        return

    response = answer(text, channel="telegram", user_id=user_id, user_name=user_name)
    send_message(config, chat_id, response)


def main() -> None:
    configure_logging()
    if not acquire_instance_lock():
        logging.warning("No se inicia otra instancia: Mar-IA Telegram ya esta activo.")
        return
    init_store()
    print("Mar-IA Telegram iniciado.")

    offset = None
    last_config_signature = None
    while True:
        try:
            config = get_telegram_config()
            if not config.enabled or not config.token:
                time.sleep(10)
                continue

            config_signature = (
                config.token,
                config.api_url,
                tuple(sorted(config.allowed_chat_ids)),
                config.allow_all_chats,
            )
            if config_signature != last_config_signature:
                logging.info(
                    "Configuracion Telegram recargada. URL: %s. Chats: %s",
                    config.api_url,
                    "todos" if config.allow_all_chats else ",".join(sorted(config.allowed_chat_ids)),
                )
                last_config_signature = config_signature
                offset = None

            payload = {"timeout": 30}
            if offset is not None:
                payload["offset"] = offset
            data = telegram_request(config, "getUpdates", payload, timeout=40)
            for update in data.get("result", []):
                message = update.get("message") or update.get("edited_message")
                if message:
                    handle_message(config, message)
                offset = update["update_id"] + 1
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
