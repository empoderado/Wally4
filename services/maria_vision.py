from __future__ import annotations

import base64
import logging
from pathlib import Path
import requests

from services.maria_ai import _settings


def encode_image(image_path: Path) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def transcribe_image(image_path: Path, caption: str = "") -> str | None:
    settings = _settings()
    api_key = settings.get("api_key")
    if not api_key:
        logging.error("No se pudo procesar la imagen: maria_api_key no esta configurada.")
        return None

    base_url = settings.get("base_url") or "https://api.openai.com/v1"

    try:
        base64_image = encode_image(image_path)
    except Exception as exc:
        logging.exception("Error al codificar la imagen a base64: %s", exc)
        return None

    prompt = (
        "Eres un copiloto comercial experto para la app Wally. El usuario te envía la foto de una prenda de vestir, "
        "de su etiqueta (donde suele haber códigos de referencia como S506345, DFS740180A, etc.) o de una captura de pantalla. "
        "Además, opcionalmente te da un texto explicativo (caption).\n"
        "Tu objetivo es realizar OCR y análisis de la imagen para extraer el código del producto (ej. S506345) y formular la pregunta "
        "escrita en español que el usuario le haría a Wally para obtener la información solicitada.\n"
        "REGLAS:\n"
        "1. Si el usuario pide el 'inventario' (o no especifica nada), la pregunta debe ser: 'inventario de la referencia [CODIGO]'. "
        "Si indica una sucursal en el caption (ej. 'en Oakland'), inclúyela: 'inventario de la referencia [CODIGO] en Oakland'.\n"
        "2. Si el usuario pide el 'precio' u otra consulta de ventas en el caption, formúlala adecuadamente (ej: 'precio de la referencia [CODIGO]').\n"
        "3. Si no detectas ningún código de referencia, intenta extraer una descripción física de la prenda (ej. 'jean negro') "
        "y formula la pregunta usándola.\n"
        "4. Responde ÚNICAMENTE con la pregunta final formulada. No agregues ninguna explicación, saludo ni formato adicional."
    )

    user_content = [
        {
            "type": "text",
            "text": f"{prompt}\n\nCaption del usuario: '{caption}'" if caption else prompt,
        },
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_image}"
            },
        },
    ]

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": user_content,
            }
        ],
        "max_tokens": 150,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        response = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        res_json = response.json()
        result = res_json["choices"][0]["message"]["content"].strip()
        # Clean any quotes or formatting the model might have returned
        result = result.strip('"`\' ')
        return result
    except Exception as exc:
        logging.exception("Error al llamar a OpenAI Vision API: %s", exc)
        return None
