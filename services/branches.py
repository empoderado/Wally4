from __future__ import annotations

from datetime import datetime
from threading import RLock

import pandas as pd

from services.local_store import connect


BRANCH_ALIASES = {
    "PARQUE LAS AMERICAS": "AMERICAS",
    "PARQUE LAS AMÉRICAS": "AMERICAS",
    "PARQUE LAS AMÃ‰RICAS": "AMERICAS",
    "ON-LINE": "ONLINE",
    "NARANJO": "NARANJO MALL",
}
_CONFIG_LOCK = RLock()
_CONFIG_CACHE: dict[str, bool] | None = None


def _ensure_config_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_sucursal_config (
            sucursal TEXT PRIMARY KEY,
            activa INTEGER NOT NULL DEFAULT 1,
            actualizado_en TEXT NOT NULL
        )
        """
    )


def normalize_branch(value: object) -> str:
    branch = str(value or "").strip().upper()
    return BRANCH_ALIASES.get(branch, branch)


def load_branch_config(refresh: bool = False) -> dict[str, bool]:
    global _CONFIG_CACHE
    with _CONFIG_LOCK:
        if _CONFIG_CACHE is not None and not refresh:
            return dict(_CONFIG_CACHE)
        conn = connect()
        try:
            _ensure_config_table(conn)
            rows = conn.execute("SELECT sucursal, activa FROM app_sucursal_config").fetchall()
        finally:
            conn.close()
        _CONFIG_CACHE = {normalize_branch(row["sucursal"]): bool(row["activa"]) for row in rows}
        return dict(_CONFIG_CACHE)


def active_branches() -> list[str] | None:
    config = load_branch_config()
    if not config:
        return None
    return sorted(branch for branch, active in config.items() if active)


def inactive_branches() -> list[str]:
    return sorted(branch for branch, active in load_branch_config().items() if not active)


def save_branch_config(frame: pd.DataFrame) -> None:
    global _CONFIG_CACHE
    now = datetime.now().isoformat(timespec="seconds")
    rows = []
    for _, row in frame.iterrows():
        branch = normalize_branch(row.get("Sucursal", ""))
        if branch:
            rows.append((branch, 1 if bool(row.get("Activa", True)) else 0, now))
    conn = connect()
    try:
        _ensure_config_table(conn)
        conn.executemany(
            """
            INSERT INTO app_sucursal_config (sucursal, activa, actualizado_en)
            VALUES (?, ?, ?)
            ON CONFLICT(sucursal) DO UPDATE SET
                activa = excluded.activa,
                actualizado_en = excluded.actualizado_en
            """,
            rows,
        )
        conn.commit()
    finally:
        conn.close()
    with _CONFIG_LOCK:
        _CONFIG_CACHE = None
    from services import db

    db.clear_query_cache()


def branch_config_frame(branches: list[str]) -> pd.DataFrame:
    config = load_branch_config()
    normalized = sorted({normalize_branch(branch) for branch in branches if normalize_branch(branch)})
    return pd.DataFrame(
        [{"Sucursal": branch, "Activa": bool(config.get(branch, True))} for branch in normalized]
    )


def discover_official_branches() -> list[str]:
    from services import db

    sources = [
        (db.VIEW_VENTAS, "Sucursal"),
        (db.VIEW_EXISTENCIA, "Sucursal"),
        (db.VIEW_ENTRADAS, "Sucursal"),
        (db.VIEW_CRM, "SucursalPreferida"),
        (db.VIEW_AUDITORIA_CAMBIO_VENDEDOR, "Sucursal"),
    ]
    branches: set[str] = set()
    for view_name, column_name in sources:
        try:
            frame = db.read_sql(
                f"""
                SELECT DISTINCT {column_name} AS Sucursal
                FROM {view_name}
                WHERE {column_name} IS NOT NULL
                  AND LTRIM(RTRIM(CAST({column_name} AS varchar(250)))) <> ''
                """,
                apply_branch_filter=False,
            )
            branches.update(normalize_branch(value) for value in frame["Sucursal"].dropna().tolist())
        except Exception:
            continue
    branches.update(load_branch_config().keys())
    return sorted(branch for branch in branches if branch)


def sql_excluded_branch_values() -> list[str]:
    inactive = inactive_branches()
    aliases_by_branch: dict[str, set[str]] = {}
    for alias, canonical in BRANCH_ALIASES.items():
        aliases_by_branch.setdefault(canonical, set()).add(alias)
    values: set[str] = set()
    for branch in inactive:
        values.add(branch)
        values.update(aliases_by_branch.get(branch, set()))
    return sorted(values)


def filter_frame(data: pd.DataFrame, columns: list[str] | tuple[str, ...]) -> pd.DataFrame:
    inactive = set(inactive_branches())
    if not inactive or data.empty:
        return data
    column = next((candidate for candidate in columns if candidate in data.columns), None)
    if column is None:
        return data
    normalized = data[column].map(normalize_branch)
    return data[~normalized.isin(inactive)].reset_index(drop=True)
