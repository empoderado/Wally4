from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import requests

from services import db
from services.env import env_value
from services.local_store import connect, init_store
from services.view_schema import required_columns


def ok(label: str, message: str) -> None:
    print(f"[OK] {label}: {message}")


def warn(label: str, message: str) -> None:
    print(f"[AVISO] {label}: {message}")


def fail(label: str, message: str) -> None:
    print(f"[ERROR] {label}: {message}")


def check_sqlite() -> None:
    try:
        init_store()
        conn = connect()
        row = conn.execute("SELECT COUNT(*) AS total FROM app_parametros").fetchone()
        conn.close()
        ok("SQLite", f"base local operativa, parametros: {row['total']}")
    except Exception as exc:
        fail("SQLite", str(exc))


def check_sql() -> None:
    is_mock = db.use_mock_data()
    requested_mock = db.mock_data_requested()
    ok("Modo datos", "simulado" if is_mock else "SQL Server real")
    ok("USE_MOCK_DATA solicitado", "si" if requested_mock else "no")
    ok("USE_MOCK_DATA efectivo", "si" if is_mock else "no")
    if requested_mock and not is_mock:
        warn("Datos", "USE_MOCK_DATA esta en yes, pero APP_ENV=production lo bloquea.")
    if is_mock:
        fail("Datos", "USE_MOCK_DATA efectivo esta activo. En servidor no debe usarse para reportes reales.")
    success, message = db.test_connection()
    if success:
        ok("SQL", message)
    else:
        fail("SQL", message)
        return

    for view in sorted(db.AUTHORIZED_VIEWS):
        try:
            frame = db.read_sql(f"SELECT TOP 0 * FROM {view}")
            ok(view, f"consulta correcta, columnas: {len(frame.columns)}")
            required = required_columns(view)
            if required:
                missing = sorted(required - set(frame.columns))
                if missing:
                    fail(f"{view} esquema", "faltan columnas oficiales: " + ", ".join(missing))
                else:
                    ok(f"{view} esquema", "columnas oficiales completas")
        except Exception as exc:
            fail(view, str(exc))


def check_telegram() -> None:
    token = env_value("TELEGRAM_BOT_TOKEN")
    if not token:
        warn("Telegram", "TELEGRAM_BOT_TOKEN no esta configurado")
        return
    try:
        response = requests.post(f"https://api.telegram.org/bot{token}/getMe", timeout=15)
        response.raise_for_status()
        data = response.json()
        if data.get("ok"):
            result = data.get("result", {})
            ok("Telegram", f"bot conectado: @{result.get('username', 'sin_usuario')}")
        else:
            fail("Telegram", str(data))
    except Exception as exc:
        fail("Telegram", str(exc))


def main() -> None:
    print("Diagnostico WallyAgent")
    print("=====================")
    print(f"APP_ENV={env_value('APP_ENV', 'production')}")
    print(f"USE_MOCK_DATA={env_value('USE_MOCK_DATA', 'no')}")
    print(f"APP_HOST={env_value('APP_HOST', '127.0.0.1')}")
    print(f"APP_PORT={env_value('APP_PORT', '8503')}")
    check_sqlite()
    check_sql()
    check_telegram()


if __name__ == "__main__":
    main()
