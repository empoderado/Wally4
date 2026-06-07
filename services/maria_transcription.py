from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import requests

from services.env import load_app_env
from services.local_store import get_param


DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
MAX_AUDIO_BYTES = 20 * 1024 * 1024
TRANSCRIPTION_PROMPT = (
    "La grabacion contiene una consulta en espanol sobre la aplicacion comercial Wally. "
    "Transcribe literalmente y conserva estos nombres propios y terminos: Mar-IA, Wally, "
    "Merchan, Jean, Bolsos, Basshert, Oakland, Chiquimula, Pradera, Majadas, Naranjo Mall, "
    "Escuintla, Parque Las Americas, On-Line, asesora, vendedor, sucursal, embarque, "
    "referencia, inventario, unidades, venta neta, ticket promedio, UPT y margen."
)


def transcribe_audio(audio_path: Path, original_name: str = "audio.ogg") -> str:
    settings = _settings()
    errors: list[str] = []

    if settings["provider"] == "openai" and settings["api_key"]:
        try:
            return _transcribe_openai(audio_path, original_name, settings)
        except Exception as exc:
            errors.append(f"OpenAI: {exc}")

    if settings["local_enabled"]:
        try:
            return _transcribe_local(audio_path, settings["local_model"])
        except Exception as exc:
            errors.append(f"Local: {exc}")

    if not errors:
        raise RuntimeError(
            "No hay un proveedor de transcripcion disponible. "
            "Configure una API key o active faster-whisper local."
        )
    raise RuntimeError("No fue posible transcribir el audio. " + " | ".join(errors))


def _transcribe_openai(audio_path: Path, original_name: str, settings: dict) -> str:
    with audio_path.open("rb") as audio_file:
        response = requests.post(
            f"{settings['base_url'].rstrip('/')}/audio/transcriptions",
            headers={"Authorization": f"Bearer {settings['api_key']}"},
            data={
                "model": settings["model"],
                "language": "es",
                "response_format": "json",
                "prompt": TRANSCRIPTION_PROMPT,
            },
            files={
                "file": (
                    original_name or audio_path.name,
                    audio_file,
                    "application/octet-stream",
                )
            },
            timeout=120,
        )
    if not response.ok:
        try:
            detail = response.json().get("error", {}).get("message", "")
        except ValueError:
            detail = ""
        suffix = f": {detail}" if detail else ""
        raise RuntimeError(f"HTTP {response.status_code}{suffix}")
    text = str(response.json().get("text", "")).strip()
    if not text:
        raise RuntimeError("El proveedor devolvio una transcripcion vacia.")
    return text


def _transcribe_local(audio_path: Path, model_name: str) -> str:
    model = _local_model(model_name)
    segments, _ = model.transcribe(
        str(audio_path),
        language="es",
        vad_filter=True,
        beam_size=5,
    )
    text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
    if not text:
        raise RuntimeError("El audio no contiene voz reconocible.")
    return text


@lru_cache(maxsize=2)
def _local_model(model_name: str):
    from faster_whisper import WhisperModel

    return WhisperModel(model_name, device="cpu", compute_type="int8")


def _settings() -> dict:
    load_app_env()
    api_key = (
        get_param("maria_api_key", "")
        or os.getenv("MARIA_API_KEY", "")
        or os.getenv("OPENAI_API_KEY", "")
    ).strip()
    base_url = (
        get_param("maria_base_url", "")
        or os.getenv("MARIA_BASE_URL", "")
        or DEFAULT_OPENAI_BASE_URL
    ).strip()
    return {
        "provider": get_param(
            "maria_transcription_provider",
            os.getenv("MARIA_TRANSCRIPTION_PROVIDER", "openai"),
        ).strip().lower(),
        "model": get_param(
            "maria_transcription_model",
            os.getenv("MARIA_TRANSCRIPTION_MODEL", "gpt-4o-transcribe"),
        ).strip()
        or "gpt-4o-transcribe",
        "api_key": api_key,
        "base_url": base_url,
        "local_enabled": get_param(
            "maria_local_transcription_enabled",
            os.getenv("MARIA_LOCAL_TRANSCRIPTION_ENABLED", "yes"),
        ).strip().lower()
        in {"1", "yes", "si", "true", "on"},
        "local_model": get_param(
            "maria_local_transcription_model",
            os.getenv("MARIA_LOCAL_TRANSCRIPTION_MODEL", "small"),
        ).strip()
        or "small",
    }
