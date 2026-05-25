from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

try:
    import pyodbc
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Falta instalar pyodbc. Ejecute primero el comando de inicio de servicios de esta carpeta.") from exc

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from scripts.apply_wallybd_sql import connection_string, execute_file, env_value, resolve_sql_driver


SQL_FILES = [
    "10_refresh_mirror_tables.sql",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Refrescar tablas Mirror de WallyBD desde StudioF.")
    parser.add_argument("--app-path", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()

    app_path = Path(args.app_path).resolve()
    env_path = app_path / ".env"
    sql_dir = app_path / "database" / "wallybd"
    if not env_path.exists():
        raise SystemExit(f"No existe .env en {app_path}")
    if not sql_dir.exists():
        raise SystemExit(f"No existe carpeta SQL: {sql_dir}")

    load_dotenv(env_path)
    print(f"App: {app_path}")
    print(f"SQL_SERVER: {env_value('SQL_SERVER')}")
    print(f"SQL_DATABASE destino: WallyBD")
    print(f"Driver efectivo: {resolve_sql_driver(env_value('SQL_DRIVER', 'ODBC Driver 17 for SQL Server'))}")

    conn = pyodbc.connect(connection_string("WallyBD"), timeout=30, autocommit=True)
    try:
        cursor = conn.cursor()
        for file_name in SQL_FILES:
            execute_file(cursor, sql_dir / file_name)
    finally:
        conn.close()

    print("\n[OK] Tablas Mirror de WallyBD refrescadas.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
