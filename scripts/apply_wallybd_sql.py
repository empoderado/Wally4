from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

try:
    import pyodbc
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Falta instalar pyodbc. Ejecute primero el comando de inicio de servicios de esta carpeta.") from exc


SQL_FILES = [
    "00_create_wallybd.sql",
    "09b_create_source_views_from_studiof_tables.sql",
    "09_create_mirror_tables.sql",
    "09a_create_admin_refresh_log.sql",
    "10_refresh_mirror_tables.sql",
    "11_create_mirror_indexes.sql",
    "01_create_mirror_views.sql",
    "02_create_vw_AuditoriaCambioVendedor.sql",
    "03_smoke_tests.sql",
    "05_validar_contrato_wallybd.sql",
    "06_create_audit_validation_tables.sql",
    "07_seed_audit_validation_rules.sql",
    "12_seed_audit_validation_cases.sql",
]


def env_value(key: str, default: str = "") -> str:
    import os

    return os.getenv(key, default).strip()


def resolve_sql_driver(preferred_driver: str) -> str:
    installed = set(pyodbc.drivers())
    if preferred_driver in installed:
        return preferred_driver
    for candidate in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "SQL Server"):
        if candidate in installed:
            return candidate
    return preferred_driver


def connection_string(database: str = "master") -> str:
    driver = resolve_sql_driver(env_value("SQL_DRIVER", "ODBC Driver 17 for SQL Server"))
    server = env_value("SQL_SERVER")
    username = env_value("SQL_USERNAME")
    password = env_value("SQL_PASSWORD")
    trusted = env_value("SQL_TRUSTED_CONNECTION", "yes").lower() in {"yes", "true", "1", "si"}
    if not server:
        raise RuntimeError("Configure SQL_SERVER en .env")
    parts = [f"DRIVER={{{driver}}}", f"SERVER={server}", f"DATABASE={database}", "TrustServerCertificate=yes"]
    if trusted:
        parts.append("Trusted_Connection=yes")
    else:
        parts.extend([f"UID={username}", f"PWD={password}"])
    return ";".join(parts)


def split_batches(sql_text: str) -> list[str]:
    batches: list[str] = []
    current: list[str] = []
    in_block_comment = False
    for line in sql_text.splitlines():
        stripped = line.strip()
        starts_comment = "/*" in stripped
        ends_comment = "*/" in stripped
        is_go = re.match(r"^\s*GO\s*(?:--.*)?$", line, flags=re.IGNORECASE)
        if is_go and not in_block_comment:
            batch = "\n".join(current).strip()
            if batch:
                batches.append(batch)
            current = []
        else:
            current.append(line)
        if starts_comment and not ends_comment:
            in_block_comment = True
        if ends_comment:
            in_block_comment = False
    batch = "\n".join(current).strip()
    if batch:
        batches.append(batch)
    return batches


def execute_file(cursor, path: Path) -> None:
    print(f"\n== {path.name} ==")
    sql_text = path.read_text(encoding="utf-8-sig")
    for index, batch in enumerate(split_batches(sql_text), start=1):
        print(f"Ejecutando lote {index}...")
        cursor.execute(batch)
        if cursor.description:
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
            print(" | ".join(columns))
            for row in rows[:20]:
                print(" | ".join("" if value is None else str(value) for value in row))
            if len(rows) > 20:
                print(f"... {len(rows) - 20} fila(s) adicionales")
        while cursor.nextset():
            if cursor.description:
                columns = [column[0] for column in cursor.description]
                rows = cursor.fetchall()
                print(" | ".join(columns))
                for row in rows[:20]:
                    print(" | ".join("" if value is None else str(value) for value in row))


def main() -> int:
    parser = argparse.ArgumentParser(description="Crear o actualizar objetos WallyBD para WallyAgent 4.0.")
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
    print(f"Driver efectivo: {resolve_sql_driver(env_value('SQL_DRIVER', 'ODBC Driver 17 for SQL Server'))}")

    conn = pyodbc.connect(connection_string("master"), timeout=30, autocommit=True)
    try:
        cursor = conn.cursor()
        for file_name in SQL_FILES:
            execute_file(cursor, sql_dir / file_name)
    finally:
        conn.close()

    print("\n[OK] WallyBD validada/actualizada.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
