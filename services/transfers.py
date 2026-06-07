from __future__ import annotations

from datetime import datetime

import pandas as pd

from services import db
from services.branches import filter_frame
from services.local_store import connect


DEFAULT_BRANCH_ORDER = [
    "OAKLAND",
    "CHIQUIMULA",
    "PRADERA",
    "AMERICAS",
    "PARQUE LAS AMERICAS",
    "MAJADAS",
    "NARANJO MALL",
    "ESCUINTLA",
    "ONLINE",
    "ON-LINE",
    "BASSHERT",
]


def normalize_branch(value: str) -> str:
    text = str(value or "").strip().upper()
    if text in {"PARQUE LAS AMERICAS", "PARQUE LAS AMÉRICAS"}:
        return "AMERICAS"
    if text == "ON-LINE":
        return "ONLINE"
    return text


def display_branch(value: str) -> str:
    normalized = normalize_branch(value)
    if normalized == "AMERICAS":
        return "AMERICAS"
    if normalized == "ONLINE":
        return "ONLINE"
    return normalized


def branch_sort_key(branch: str) -> tuple[int, str]:
    normalized = normalize_branch(branch)
    normalized_order = [normalize_branch(item) for item in DEFAULT_BRANCH_ORDER]
    if normalized in normalized_order:
        return normalized_order.index(normalized), normalized
    return len(normalized_order), normalized


def official_branches() -> list[str]:
    frame = db.read_sql(
        f"""
        SELECT DISTINCT Sucursal
        FROM {db.VIEW_EXISTENCIA}
        WHERE Sucursal IS NOT NULL
          AND LTRIM(RTRIM(CAST(Sucursal AS varchar(250)))) <> ''
        """
    )
    branches = sorted({display_branch(value) for value in frame["Sucursal"].dropna().tolist()}, key=branch_sort_key)
    return branches


def official_lines() -> list[str]:
    frame = db.read_sql(
        f"""
        SELECT DISTINCT Linea
        FROM {db.VIEW_EXISTENCIA}
        WHERE Linea IS NOT NULL
          AND LTRIM(RTRIM(CAST(Linea AS varchar(250)))) <> ''
        ORDER BY Linea
        """
    )
    return [str(value).strip() for value in frame["Linea"].dropna().tolist()]


def official_sublines(lines: list[str] | None = None) -> list[str]:
    where = ""
    if lines:
        where = f"AND Linea IN ({db.sql_literal_list(lines)})"
    frame = db.read_sql(
        f"""
        SELECT DISTINCT DescSubLinea
        FROM {db.VIEW_EXISTENCIA}
        WHERE DescSubLinea IS NOT NULL
          AND LTRIM(RTRIM(CAST(DescSubLinea AS varchar(250)))) <> ''
          {where}
        ORDER BY DescSubLinea
        """
    )
    return [str(value).strip() for value in frame["DescSubLinea"].dropna().tolist()]


def load_branch_priorities(branches: list[str] | None = None) -> pd.DataFrame:
    branches = branches or []
    conn = connect()
    try:
        existing = pd.read_sql_query(
            "SELECT sucursal AS Sucursal, prioridad AS Prioridad FROM traslado_prioridad_sucursal",
            conn,
        )
    finally:
        conn.close()

    if existing.empty:
        existing = pd.DataFrame(columns=["Sucursal", "Prioridad"])
    existing["Sucursal"] = existing["Sucursal"].map(display_branch)
    existing = existing.drop_duplicates("Sucursal", keep="last")
    existing = filter_frame(existing, ["Sucursal"])
    priorities = dict(zip(existing["Sucursal"], existing["Prioridad"]))

    rows = []
    for branch in sorted({display_branch(item) for item in branches} | set(priorities), key=branch_sort_key):
        rows.append({"Sucursal": branch, "Prioridad": int(priorities.get(branch, 0) or 0)})
    return pd.DataFrame(rows)


def save_branch_priorities(frame: pd.DataFrame) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = connect()
    try:
        for _, row in frame.iterrows():
            branch = display_branch(row.get("Sucursal", ""))
            if not branch:
                continue
            try:
                priority = int(row.get("Prioridad", 0) or 0)
            except Exception:
                priority = 0
            priority = max(0, priority)
            conn.execute(
                """
                INSERT INTO traslado_prioridad_sucursal (sucursal, prioridad, actualizado_en)
                VALUES (?, ?, ?)
                ON CONFLICT(sucursal) DO UPDATE SET
                    prioridad = excluded.prioridad,
                    actualizado_en = excluded.actualizado_en
                """,
                (branch, priority, now),
            )
        conn.commit()
    finally:
        conn.close()


def load_inventory() -> pd.DataFrame:
    frame = db.read_sql(
        f"""
        SELECT
            CodEmbarqueAbreviado AS EMB,
            Linea,
            DescSubLinea AS Sublinea,
            Referencia,
            Color,
            Talla,
            Sucursal,
            MIN(ISNULL(TVida, 999999)) AS TVida,
            SUM(ISNULL(ExistenciaDisponible, 0)) AS Existencia
        FROM {db.VIEW_EXISTENCIA}
        WHERE ISNULL(ExistenciaDisponible, 0) > 0
          AND CodEmbarqueAbreviado IS NOT NULL
          AND Referencia IS NOT NULL
          AND Color IS NOT NULL
          AND Talla IS NOT NULL
        GROUP BY
            CodEmbarqueAbreviado,
            Linea,
            DescSubLinea,
            Referencia,
            Color,
            Talla,
            Sucursal
        """
    )
    if frame.empty:
        return frame
    frame["Sucursal"] = frame["Sucursal"].map(display_branch)
    frame["Linea"] = frame["Linea"].astype(str).str.strip()
    frame["Sublinea"] = frame["Sublinea"].astype(str).str.strip()
    frame["Existencia"] = pd.to_numeric(frame["Existencia"], errors="coerce").fillna(0).astype(int)
    frame["TVida"] = pd.to_numeric(frame["TVida"], errors="coerce").fillna(999999).astype(int)
    return frame


def load_reference_rotation() -> pd.DataFrame:
    frame = db.read_sql(
        f"""
        WITH Entradas AS
        (
            SELECT
                CAST(Sucursal AS varchar(250)) COLLATE DATABASE_DEFAULT AS Sucursal,
                CAST(Referencia AS varchar(250)) COLLATE DATABASE_DEFAULT AS Referencia,
                SUM(ISNULL(UnidadesEntrada, 0)) AS UnidadesEntradaReferencia
            FROM {db.VIEW_ENTRADAS}
            WHERE Referencia IS NOT NULL
            GROUP BY Sucursal, Referencia
        ),
        Ventas AS
        (
            SELECT
                CAST(Sucursal AS varchar(250)) COLLATE DATABASE_DEFAULT AS Sucursal,
                CAST(Referencia AS varchar(250)) COLLATE DATABASE_DEFAULT AS Referencia,
                SUM(ISNULL(Unidades, 0)) AS UnidadesFacturadasReferencia
            FROM {db.VIEW_VENTAS}
            WHERE Trn = 'FV'
              AND Referencia IS NOT NULL
            GROUP BY Sucursal, Referencia
        )
        SELECT
            COALESCE(e.Sucursal, v.Sucursal) AS Sucursal,
            COALESCE(e.Referencia, v.Referencia) AS Referencia,
            ISNULL(e.UnidadesEntradaReferencia, 0) AS UnidadesEntradaReferencia,
            ISNULL(v.UnidadesFacturadasReferencia, 0) AS UnidadesFacturadasReferencia,
            CASE
                WHEN ISNULL(e.UnidadesEntradaReferencia, 0) = 0 THEN 0
                ELSE CAST(ISNULL(v.UnidadesFacturadasReferencia, 0) AS decimal(18, 6))
                     / NULLIF(e.UnidadesEntradaReferencia, 0)
            END AS RotacionReferencia
        FROM Entradas e
        FULL OUTER JOIN Ventas v
            ON e.Sucursal = v.Sucursal
           AND e.Referencia = v.Referencia
        """
    )
    if frame.empty:
        return frame
    frame["Sucursal"] = frame["Sucursal"].map(display_branch)
    frame["Referencia"] = frame["Referencia"].astype(str).str.strip()
    return frame


def generate_fifo_xl(
    inventory: pd.DataFrame,
    priorities: pd.DataFrame,
    max_units: int,
    destination_branches: list[str] | None = None,
    rotation_metrics: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if inventory.empty or max_units <= 0:
        return output_columns(pd.DataFrame(), priorities)

    priority_map = {
        display_branch(row["Sucursal"]): int(row["Prioridad"])
        for _, row in priorities.iterrows()
        if int(row.get("Prioridad", 0) or 0) > 0
    }
    active_branches = sorted(priority_map, key=lambda branch: (priority_map[branch], branch_sort_key(branch)))
    if not active_branches:
        return output_columns(pd.DataFrame(), priorities)

    selected_destinations = {display_branch(item) for item in (destination_branches or active_branches)}
    selected_destinations = selected_destinations & set(active_branches)
    if not selected_destinations:
        return output_columns(pd.DataFrame(), priorities)

    inv = inventory[inventory["Sucursal"].isin(active_branches)].copy()
    if inv.empty:
        return output_columns(pd.DataFrame(), priorities)

    sku_cols = ["EMB", "Linea", "Referencia", "Color", "Talla"]
    stock = {
        tuple(row[col] for col in sku_cols) + (row["Sucursal"],): int(row["Existencia"])
        for _, row in inv.iterrows()
    }
    rotation_source = rotation_metrics if rotation_metrics is not None and not rotation_metrics.empty else inv
    rotation = {
        (str(row["Referencia"]), display_branch(row["Sucursal"])): float(row.get("RotacionReferencia", 0) or 0)
        for _, row in rotation_source.iterrows()
    }
    life = {
        (tuple(row[col] for col in sku_cols), row["Sucursal"]): int(row.get("TVida", 999999) or 999999)
        for _, row in inv.iterrows()
    }

    branch_columns = sorted(active_branches, key=branch_sort_key)
    sku_order = (
        inv.groupby(sku_cols, dropna=False, as_index=False)
        .agg(TVida=("TVida", "min"), TotalExistencia=("Existencia", "sum"))
        .sort_values(["TVida", "EMB", "Linea", "Referencia", "Color", "Talla"], ascending=[True, True, True, True, True, True])
    )

    rows = []
    moved_units = 0

    for _, sku in sku_order.iterrows():
        if moved_units >= max_units:
            break
        sku_key = tuple(sku[col] for col in sku_cols)
        snapshot = {
            branch: int(stock.get(sku_key + (branch,), 0))
            for branch in branch_columns
        }

        destinations = sorted(
            [branch for branch in active_branches if branch in selected_destinations and snapshot.get(branch, 0) <= 0],
            key=lambda branch: (
                -rotation.get((str(sku["Referencia"]), branch), 0),
                priority_map[branch],
                branch_sort_key(branch),
            ),
        )
        origins = sorted(
            [branch for branch in active_branches if snapshot.get(branch, 0) > 1],
            key=lambda branch: (
                rotation.get((str(sku["Referencia"]), branch), 0),
                life.get((sku_key, branch), 999999),
                -snapshot.get(branch, 0),
                branch_sort_key(branch),
            ),
        )

        for destination in destinations:
            if moved_units >= max_units:
                break
            if stock.get(sku_key + (destination,), 0) > 0:
                continue
            need = 1
            for origin in origins:
                if moved_units >= max_units or need <= 0:
                    break
                if origin == destination:
                    continue
                origin_stock = int(stock.get(sku_key + (origin,), 0))
                if origin_stock <= 1:
                    continue

                qty = min(need, origin_stock - 1, max_units - moved_units)
                if qty <= 0:
                    continue
                if origin_stock - qty <= 1:
                    qty = min(origin_stock, max_units - moved_units)
                if qty <= 0:
                    continue

                row = {
                    "EMB": sku["EMB"],
                    "Linea": sku["Linea"],
                    "Referencia": sku["Referencia"],
                    "Color": sku["Color"],
                    "Talla": sku["Talla"],
                }
                for branch in branch_columns:
                    row[f"EXISTENCIA {branch}"] = snapshot.get(branch, 0)
                row["ORIGEN TIENDA QUE DESPACHA"] = origin
                row["DESTINO TIENDA QUE RECIBE"] = destination
                row["CANTIDAD"] = int(qty)
                rows.append(row)

                stock[sku_key + (origin,)] = origin_stock - qty
                stock[sku_key + (destination,)] = int(stock.get(sku_key + (destination,), 0)) + qty
                moved_units += qty
                need -= qty

    return output_columns(pd.DataFrame(rows), priorities)


def output_columns(frame: pd.DataFrame, priorities: pd.DataFrame) -> pd.DataFrame:
    active_branches = [
        display_branch(row["Sucursal"])
        for _, row in priorities.iterrows()
        if int(row.get("Prioridad", 0) or 0) > 0
    ]
    branch_columns = [f"EXISTENCIA {branch}" for branch in sorted(set(active_branches), key=branch_sort_key)]
    cols = ["EMB", "Linea", "Referencia", "Color", "Talla"] + branch_columns + [
        "ORIGEN TIENDA QUE DESPACHA",
        "DESTINO TIENDA QUE RECIBE",
        "CANTIDAD",
    ]
    for col in cols:
        if col not in frame.columns:
            frame[col] = ""
    return frame[cols]
