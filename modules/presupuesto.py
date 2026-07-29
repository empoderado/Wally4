from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html import escape

import pandas as pd
import streamlit as st

from services import db
from services.branches import filter_frame
from services.catalog import get_code
from services.exports import dataframe_to_excel_bytes, export_filename
from services.formatting import money, number
from services.local_store import connect, read_table
from services.ui import code_footer, display_table, page_title, section_title


DIAS_ES = {
    0: "lunes",
    1: "martes",
    2: "miercoles",
    3: "jueves",
    4: "viernes",
    5: "sabado",
    6: "domingo",
}

BRANCH_REQUIRED = ["codigoSucursal", "nombreSucursal", "fecha", "unidades", "valorPresupuesto"]
SELLER_REQUIRED = ["idVendedor", "nombreVendedor", "idSucursal", "nombreSucursal", "fecha", "unidades", "vrPresupuesto"]
SELLER_UPLOAD_COLUMNS = SELLER_REQUIRED.copy()
LINE_BRANCH_REQUIRED = ["fecha", "idLinea", "linea", "unidades", "ventaQ", "idSucursal", "sucursal"]
LINE_BRANCH_UPLOAD_COLUMNS = ["Fecha", "Idlinea", "CODLinea", "Unidades", "Quetzal", "Idsucursal", "Sucursal"]
LINE_BRANCH_UPLOAD_RENAME = dict(zip(LINE_BRANCH_UPLOAD_COLUMNS, LINE_BRANCH_REQUIRED))
LINE_BRANCH_COLUMN_ALIASES = {
    "fecha": "fecha",
    "idlinea": "idLinea",
    "id linea": "idLinea",
    "linea": "linea",
    "línea": "linea",
    "unidades": "unidades",
    "unidad": "unidades",
    "ventaq": "ventaQ",
    "venta q": "ventaQ",
    "quetzal": "ventaQ",
    "quetzales": "ventaQ",
    "idsucursal": "idSucursal",
    "id sucursal": "idSucursal",
    "sucursal": "sucursal",
}
BRANCH_ORDER = [
    "OAKLAND",
    "CHIQUIMULA",
    "PRADERA",
    "LAS AMERICAS",
    "MAJADAS",
    "NARANJO MALL",
    "ESCUINTLA",
    "VIDERE",
    "ONLINE",
    "BASSHERT",
]


def _budget_css() -> None:
    st.markdown(
        """
        <style>
        .wally-budget-wrap {
            width: 100%;
            overflow-x: auto;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            background: #ffffff;
            box-shadow: 0 2px 10px rgba(15, 23, 42, .04);
        }
        .wally-budget-title {
            text-align: center;
            font-weight: 850;
            color: #0f172a;
            padding: 10px 8px 8px 8px;
            letter-spacing: 0;
        }
        table.wally-budget {
            border-collapse: collapse;
            width: max-content;
            min-width: 100%;
            font-size: 12px;
        }
        table.wally-budget th, table.wally-budget td {
            border: 1px solid #cbd5e1;
            padding: 5px 7px;
            white-space: nowrap;
        }
        table.wally-budget th {
            background: #ffffff;
            color: #b91c1c;
            font-weight: 850;
            text-transform: uppercase;
            text-align: center;
        }
        table.wally-budget th.wally-total-head {
            background: #1e293b;
            color: #ffffff;
        }
        table.wally-budget td {
            text-align: right;
            color: #0f172a;
        }
        table.wally-budget td.wally-date,
        table.wally-budget td.wally-day {
            text-align: center;
        }
        table.wally-budget td.wally-day {
            text-align: left;
        }
        table.wally-budget td.wally-week {
            background: #e8eef7;
            color: #b91c1c;
            font-weight: 850;
            text-align: center;
        }
        table.wally-budget tr.wally-month-total td {
            background: #fef08a;
            font-weight: 850;
        }
        table.wally-budget tr.wally-alt td {
            background: #f1f5fb;
        }
        table.wally-budget tr.wally-sunday td {
            background: #ffe4e6;
        }
        table.wally-budget tr.wally-week-start td {
            border-top: 2px solid #0f172a;
        }
        table.wally-budget tr.wally-subtotal td {
            background: #e0f2fe;
            color: #0f172a;
            font-weight: 850;
            border-top: 2px solid #334155;
        }
        table.wally-budget tr.wally-grand-total td {
            background: #fff7ed;
            color: #7c2d12;
            font-weight: 900;
            border-top: 2px solid #7c2d12;
        }
        table.wally-budget tr.wally-summary-total td {
            background: #dbeafe;
            color: #0f172a;
            font-weight: 900;
            border-top: 2px solid #1e293b;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _week_bounds(value: date) -> tuple[date, date]:
    start = value - timedelta(days=value.weekday())
    return start, start + timedelta(days=6)


def _week_label_map(dates: list[date]) -> dict[date, str]:
    starts = sorted({_week_bounds(item)[0] for item in dates})
    return {week_start: f"Sem {idx + 1}" for idx, week_start in enumerate(starts)}


def _enrich_dates(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    data["fecha"] = pd.to_datetime(data["fecha"], errors="coerce").dt.date
    data["anio"] = data["fecha"].map(lambda x: x.year if pd.notna(x) else None)
    data["mes"] = data["fecha"].map(lambda x: x.month if pd.notna(x) else None)
    data["dia"] = data["fecha"].map(lambda x: x.day if pd.notna(x) else None)
    data["dia_semana"] = data["fecha"].map(lambda x: DIAS_ES[x.weekday()] if pd.notna(x) else "")
    data["semana_mes"] = data["fecha"].map(lambda x: int(((x.day - 1) // 7) + 1) if pd.notna(x) else None)
    data["semana_inicio"] = data["fecha"].map(lambda x: _week_bounds(x)[0].isoformat() if pd.notna(x) else "")
    data["semana_fin"] = data["fecha"].map(lambda x: _week_bounds(x)[1].isoformat() if pd.notna(x) else "")
    return data


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    data.columns = [str(col).strip() for col in data.columns]
    return data


def _normalize_line_branch_columns(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    renamed = {}
    for col in data.columns:
        key = str(col).strip().lower()
        renamed[col] = LINE_BRANCH_COLUMN_ALIASES.get(key, str(col).strip())
    data = data.rename(columns=renamed)
    return _normalize_columns(data)


def _round_half_up_int(value) -> int | None:
    if pd.isna(value):
        return None
    try:
        return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError):
        return None


def _validate_budget_frame(df: pd.DataFrame, required: list[str], numeric_cols: list[str], key_cols: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = _normalize_columns(df)
    errors: list[dict] = []
    missing = [col for col in required if col not in data.columns]
    if missing:
        return pd.DataFrame(), pd.DataFrame([{"Fila": 0, "Error": f"Faltan columnas obligatorias: {', '.join(missing)}"}])

    data = data[required].copy()
    for col in required:
        if col not in numeric_cols and col != "fecha":
            data[col] = data[col].astype(str).str.strip()
    data["fecha"] = pd.to_datetime(data["fecha"], errors="coerce").dt.date
    for col in numeric_cols:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    valid_rows = []
    for idx, row in data.iterrows():
        row_errors = []
        for col in required:
            value = row[col]
            if col == "fecha":
                if pd.isna(value):
                    row_errors.append("fecha invalida")
            elif col in numeric_cols:
                if pd.isna(value):
                    row_errors.append(f"{col} no numerico")
            elif str(value).strip() == "" or str(value).strip().lower() == "nan":
                row_errors.append(f"{col} vacio")
        if row_errors:
            errors.append({"Fila": int(idx) + 2, "Error": "; ".join(row_errors), "Datos": json.dumps(row.to_dict(), default=str, ensure_ascii=False)})
        else:
            valid_rows.append(row.to_dict())

    valid = pd.DataFrame(valid_rows)
    if not valid.empty:
        duplicated = valid.duplicated(subset=key_cols, keep=False)
        for dup_idx, row in valid[duplicated].iterrows():
            errors.append({"Fila": int(dup_idx) + 2, "Error": "Registro duplicado dentro del Excel", "Datos": json.dumps(row.to_dict(), default=str, ensure_ascii=False)})
        valid = valid[~duplicated].copy()
        valid = _enrich_dates(valid)
    return valid, pd.DataFrame(errors)


def _validate_seller_budget_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = _normalize_columns(df)
    actual_columns = list(data.columns)
    if actual_columns != SELLER_UPLOAD_COLUMNS:
        expected = ", ".join(SELLER_UPLOAD_COLUMNS)
        received = ", ".join(actual_columns)
        return pd.DataFrame(), pd.DataFrame(
            [
                {
                    "Fila": 0,
                    "Error": (
                        "Columnas invalidas para F-PTO-02. "
                        f"El archivo debe contener exactamente estas columnas y en este orden: {expected}. "
                        f"Columnas recibidas: {received}"
                    ),
                }
            ]
        )
    return _validate_budget_frame(
        data,
        SELLER_REQUIRED,
        ["unidades", "vrPresupuesto"],
        ["idVendedor", "idSucursal", "fecha"],
    )


def _validate_line_branch_budget_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = _normalize_columns(df)
    errors: list[dict] = []
    actual_columns = list(data.columns)
    if actual_columns != LINE_BRANCH_UPLOAD_COLUMNS:
        expected = ", ".join(LINE_BRANCH_UPLOAD_COLUMNS)
        received = ", ".join(actual_columns)
        return pd.DataFrame(), pd.DataFrame(
            [
                {
                    "Fila": 0,
                    "Error": f"Columnas invalidas. El archivo debe contener exactamente estas columnas y en este orden: {expected}. Columnas recibidas: {received}",
                }
            ]
        )

    data = data.rename(columns=LINE_BRANCH_UPLOAD_RENAME)
    data = data[LINE_BRANCH_REQUIRED].copy()
    for col in ["idLinea", "linea", "idSucursal", "sucursal"]:
        data[col] = data[col].astype(str).str.strip()
    data["fecha"] = pd.to_datetime(data["fecha"], errors="coerce", dayfirst=True).dt.date
    for col in ["unidades", "ventaQ"]:
        if data[col].dtype == object:
            text = data[col].astype(str).str.strip()
            has_comma = text.str.contains(",", regex=False)
            text = text.mask(has_comma, text.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
            data[col] = text
        data[col] = pd.to_numeric(data[col], errors="coerce")
        data[col] = data[col].map(_round_half_up_int)

    valid_rows = []
    for idx, row in data.iterrows():
        row_errors = []
        if pd.isna(row["fecha"]):
            row_errors.append("fecha invalida")
        for col in ["idLinea", "linea", "idSucursal", "sucursal"]:
            value = str(row[col]).strip()
            if value == "" or value.lower() == "nan":
                row_errors.append(f"{col} vacio")
        for col in ["unidades", "ventaQ"]:
            if pd.isna(row[col]):
                row_errors.append(f"{col} no numerico")
        if row_errors:
            errors.append({"Fila": int(idx) + 2, "Error": "; ".join(row_errors), "Datos": json.dumps(row.to_dict(), default=str, ensure_ascii=False)})
        else:
            valid_rows.append(row.to_dict())

    valid = pd.DataFrame(valid_rows)
    if not valid.empty:
        duplicated = valid.duplicated(subset=["fecha", "idLinea", "idSucursal"], keep=False)
        for dup_idx, row in valid[duplicated].iterrows():
            errors.append({"Fila": int(dup_idx) + 2, "Error": "Registro duplicado dentro del Excel", "Datos": json.dumps(row.to_dict(), default=str, ensure_ascii=False)})
        valid = valid[~duplicated].copy()
        valid = _enrich_dates(valid)
    return valid, pd.DataFrame(errors)


def _log_import(tipo: str, filename: str, total: int, inserted: int, updated: int, errors: pd.DataFrame) -> None:
    conn = connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO presupuesto_importacion_log
                (tipo_importacion, nombre_archivo, total_filas, filas_insertadas, filas_actualizadas, filas_error, usuario, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (tipo, filename, total, inserted, updated, len(errors), "", datetime.now().isoformat(timespec="seconds")),
        )
        import_id = cur.lastrowid
        for _, row in errors.iterrows():
            conn.execute(
                """
                INSERT INTO presupuesto_importacion_error (importacion_id, numero_fila, mensaje_error, data_original)
                VALUES (?, ?, ?, ?)
                """,
                (import_id, int(row.get("Fila", 0)), str(row.get("Error", "")), str(row.get("Datos", ""))),
            )
        conn.commit()
    finally:
        conn.close()


def _upsert_branch_budget(df: pd.DataFrame, overwrite: bool) -> tuple[int, int, pd.DataFrame]:
    conn = connect()
    inserted = 0
    updated = 0
    errors: list[dict] = []
    now = datetime.now().isoformat(timespec="seconds")
    try:
        for idx, row in df.iterrows():
            existing = conn.execute(
                "SELECT id FROM pto_sucursal WHERE codigo_sucursal = ? AND fecha = ?",
                (row["codigoSucursal"], row["fecha"].isoformat()),
            ).fetchone()
            if existing and not overwrite:
                errors.append({"Fila": int(idx) + 2, "Error": "Ya existe presupuesto para la misma sucursal y fecha", "Datos": json.dumps(row.to_dict(), default=str, ensure_ascii=False)})
                continue
            conn.execute(
                """
                INSERT INTO pto_sucursal (
                    codigo_sucursal, nombre_sucursal, fecha, unidades, valor_presupuesto,
                    anio, mes, dia, dia_semana, semana_mes, semana_inicio, semana_fin, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(codigo_sucursal, fecha) DO UPDATE SET
                    nombre_sucursal = excluded.nombre_sucursal,
                    unidades = excluded.unidades,
                    valor_presupuesto = excluded.valor_presupuesto,
                    anio = excluded.anio,
                    mes = excluded.mes,
                    dia = excluded.dia,
                    dia_semana = excluded.dia_semana,
                    semana_mes = excluded.semana_mes,
                    semana_inicio = excluded.semana_inicio,
                    semana_fin = excluded.semana_fin,
                    updated_at = excluded.updated_at
                """,
                (
                    row["codigoSucursal"], row["nombreSucursal"], row["fecha"].isoformat(), float(row["unidades"]), float(row["valorPresupuesto"]),
                    int(row["anio"]), int(row["mes"]), int(row["dia"]), row["dia_semana"], int(row["semana_mes"]), row["semana_inicio"], row["semana_fin"], now, now,
                ),
            )
            if existing:
                updated += 1
            else:
                inserted += 1
        conn.commit()
    finally:
        conn.close()
    return inserted, updated, pd.DataFrame(errors)


def _upsert_seller_budget(df: pd.DataFrame, overwrite: bool) -> tuple[int, int, pd.DataFrame]:
    conn = connect()
    inserted = 0
    updated = 0
    errors: list[dict] = []
    now = datetime.now().isoformat(timespec="seconds")
    records = []
    try:
        existing_keys = {
            (str(row["id_vendedor"]), str(row["id_sucursal"]), str(row["fecha"]))
            for row in conn.execute("SELECT id_vendedor, id_sucursal, fecha FROM pto_vendedor").fetchall()
        }
        for idx, row in df.iterrows():
            key = (str(row["idVendedor"]), str(row["idSucursal"]), row["fecha"].isoformat())
            if key in existing_keys and not overwrite:
                errors.append({"Fila": int(idx) + 2, "Error": "Ya existe presupuesto para el mismo vendedor, sucursal y fecha", "Datos": json.dumps(row.to_dict(), default=str, ensure_ascii=False)})
                continue
            records.append(
                (
                    row["idVendedor"], row["nombreVendedor"], row["idSucursal"], row["nombreSucursal"], row["fecha"].isoformat(),
                    float(row["unidades"]), float(row["vrPresupuesto"]), int(row["anio"]), int(row["mes"]), int(row["dia"]),
                    row["dia_semana"], int(row["semana_mes"]), row["semana_inicio"], row["semana_fin"], now, now,
                )
            )
            if key in existing_keys:
                updated += 1
            else:
                inserted += 1
                existing_keys.add(key)
        if records:
            conn.executemany(
                """
                INSERT INTO pto_vendedor (
                    id_vendedor, nombre_vendedor, id_sucursal, nombre_sucursal, fecha, unidades, vr_presupuesto,
                    anio, mes, dia, dia_semana, semana_mes, semana_inicio, semana_fin, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id_vendedor, id_sucursal, fecha) DO UPDATE SET
                    nombre_vendedor = excluded.nombre_vendedor,
                    nombre_sucursal = excluded.nombre_sucursal,
                    unidades = excluded.unidades,
                    vr_presupuesto = excluded.vr_presupuesto,
                    anio = excluded.anio,
                    mes = excluded.mes,
                    dia = excluded.dia,
                    dia_semana = excluded.dia_semana,
                    semana_mes = excluded.semana_mes,
                    semana_inicio = excluded.semana_inicio,
                    semana_fin = excluded.semana_fin,
                    updated_at = excluded.updated_at
                """,
                records,
            )
        conn.commit()
    finally:
        conn.close()
    return inserted, updated, pd.DataFrame(errors)


def _upsert_line_branch_budget(df: pd.DataFrame, overwrite: bool) -> tuple[int, int, pd.DataFrame]:
    conn = connect()
    inserted = 0
    updated = 0
    errors: list[dict] = []
    now = datetime.now().isoformat(timespec="seconds")
    try:
        for idx, row in df.iterrows():
            fecha = row["fecha"].isoformat()
            existing = conn.execute(
                "SELECT id FROM pto_linea_sucursal WHERE fecha = ? AND id_linea = ? AND id_sucursal = ?",
                (fecha, str(row["idLinea"]), str(row["idSucursal"])),
            ).fetchone()
            if existing and not overwrite:
                errors.append({"Fila": int(idx) + 2, "Error": "Ya existe presupuesto para la misma linea, sucursal y fecha", "Datos": json.dumps(row.to_dict(), default=str, ensure_ascii=False)})
                continue
            conn.execute(
                """
                INSERT INTO pto_linea_sucursal (
                    fecha, id_linea, linea, unidades, venta_q, id_sucursal, sucursal,
                    anio, mes, dia, dia_semana, semana_mes, semana_inicio, semana_fin, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fecha, id_linea, id_sucursal) DO UPDATE SET
                    linea = excluded.linea,
                    unidades = excluded.unidades,
                    venta_q = excluded.venta_q,
                    sucursal = excluded.sucursal,
                    anio = excluded.anio,
                    mes = excluded.mes,
                    dia = excluded.dia,
                    dia_semana = excluded.dia_semana,
                    semana_mes = excluded.semana_mes,
                    semana_inicio = excluded.semana_inicio,
                    semana_fin = excluded.semana_fin,
                    updated_at = excluded.updated_at
                """,
                (
                    fecha,
                    str(row["idLinea"]),
                    str(row["linea"]).strip().upper(),
                    float(row["unidades"]),
                    float(row["ventaQ"]),
                    str(row["idSucursal"]),
                    str(row["sucursal"]).strip().upper(),
                    int(row["anio"]),
                    int(row["mes"]),
                    int(row["dia"]),
                    row["dia_semana"],
                    int(row["semana_mes"]),
                    row["semana_inicio"],
                    row["semana_fin"],
                    now,
                    now,
                ),
            )
            if existing:
                updated += 1
            else:
                inserted += 1
        conn.commit()
    finally:
        conn.close()
    return inserted, updated, pd.DataFrame(errors)


def _read_local_table(table: str, start_date: date, end_date: date) -> pd.DataFrame:
    conn = connect()
    try:
        data = pd.read_sql_query(
            f"SELECT * FROM {table} WHERE fecha BETWEEN ? AND ?",
            conn,
            params=(start_date.isoformat(), end_date.isoformat()),
        )
        return filter_frame(data, ["nombre_sucursal", "sucursal"])
    finally:
        conn.close()


def _real_sales_by_branch(start_date: date, end_date: date) -> pd.DataFrame:
    return db.read_sql(
        f"""
        SELECT
            CAST(Fecha AS date) AS fecha,
            Sucursal AS nombre_sucursal,
            SUM(ISNULL(Unidades, 0)) AS unidades_reales,
            SUM(ISNULL(VentaNetaQ, 0)) AS venta_real
        FROM {db.VIEW_VENTAS}
        WHERE Fecha >= ? AND Fecha < DATEADD(day, 1, ?)
          AND Trn = 'FV'
        GROUP BY CAST(Fecha AS date), Sucursal
        """,
        db.date_params(start_date, end_date),
    )


def _real_sales_by_seller(start_date: date, end_date: date) -> pd.DataFrame:
    return db.read_sql(
        f"""
        SELECT
            CAST(Fecha AS date) AS fecha,
            CAST(IdVendedor AS varchar(50)) AS id_vendedor,
            Vendedor AS nombre_vendedor,
            Sucursal AS nombre_sucursal,
            SUM(ISNULL(Unidades, 0)) AS unidades_reales,
            SUM(ISNULL(VentaNetaQ, 0)) AS venta_real
        FROM {db.VIEW_VENTAS}
        WHERE Fecha >= ? AND Fecha < DATEADD(day, 1, ?)
          AND Trn = 'FV'
        GROUP BY CAST(Fecha AS date), CAST(IdVendedor AS varchar(50)), Vendedor, Sucursal
        """,
        db.date_params(start_date, end_date),
    )


def _format_pct_display(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{float(value):,.0f}%".replace(",", ".")


def _format_money_plain(value: float | int | None) -> str:
    return number(value, 0)


def _short_branch_name(name: str) -> str:
    cleaned = str(name).strip().upper()
    if cleaned in {"PARQUE LAS AMERICAS", "PARQUE LAS AMÉRICAS", "AMERICAS"}:
        return "LAS AMERICAS"
    if cleaned in {"ON-LINE", "ON LINE"}:
        return "ONLINE"
    return cleaned


def _ordered_branches(values: list[str]) -> list[str]:
    unique = []
    for value in values:
        if pd.isna(value):
            continue
        text = str(value).strip()
        if text and text not in unique:
            unique.append(text)
    return sorted(unique, key=lambda value: (BRANCH_ORDER.index(_short_branch_name(value)) if _short_branch_name(value) in BRANCH_ORDER else 999, _short_branch_name(value)))


def _branch_matrix_dataframe(df: pd.DataFrame, start_date: date, end_date: date, value_col: str) -> pd.DataFrame:
    data = df.copy()
    if data.empty:
        return pd.DataFrame()
    data["fecha"] = pd.to_datetime(data["fecha"]).dt.date
    branches = _ordered_branches(data["nombre_sucursal"].dropna().unique().tolist())
    dates = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
    labels = _week_label_map(dates)
    pivot = data.pivot_table(index="fecha", columns="nombre_sucursal", values=value_col, aggfunc="sum", fill_value=0)

    rows = []
    current_week_start = None
    week_totals = {branch: 0.0 for branch in branches}
    week_grand = 0.0
    for day_value in dates:
        week_start, _ = _week_bounds(day_value)
        if current_week_start is not None and week_start != current_week_start:
            subtotal = {"Semana": labels[current_week_start], "Fecha": "", "Dia": "Subtotal"}
            subtotal.update({branch: week_totals[branch] for branch in branches})
            subtotal["Total"] = week_grand
            rows.append(subtotal)
            week_totals = {branch: 0.0 for branch in branches}
            week_grand = 0.0
        current_week_start = week_start
        row = {
            "Semana": labels[week_start] if day_value == week_start or day_value == start_date else "",
            "Fecha": day_value.strftime("%d/%m/%Y"),
            "Dia": DIAS_ES[day_value.weekday()],
        }
        row_total = 0.0
        for branch in branches:
            value = float(pivot.loc[day_value, branch]) if day_value in pivot.index and branch in pivot.columns else 0.0
            row[branch] = value
            week_totals[branch] += value
            row_total += value
        row["Total"] = row_total
        week_grand += row_total
        rows.append(row)
    if current_week_start is not None:
        subtotal = {"Semana": labels[current_week_start], "Fecha": "", "Dia": "Subtotal"}
        subtotal.update({branch: week_totals[branch] for branch in branches})
        subtotal["Total"] = week_grand
        rows.append(subtotal)
    total = {"Semana": "", "Fecha": "", "Dia": "Total acumulado"}
    for branch in branches:
        total[branch] = sum(float(row.get(branch, 0) or 0) for row in rows if row.get("Dia") not in {"Subtotal", "Total acumulado"})
    total["Total"] = sum(float(row.get("Total", 0) or 0) for row in rows if row.get("Dia") not in {"Subtotal", "Total acumulado"})
    rows.append(total)
    return pd.DataFrame(rows)


def _branch_matrix_html(df: pd.DataFrame, start_date: date, end_date: date, value_col: str, title: str) -> str:
    if df.empty:
        return f"<div class='wally-budget-wrap'><div class='wally-budget-title'>{escape(title)}</div><p style='padding:12px'>No hay presupuesto cargado para el rango seleccionado.</p></div>"

    data = df.copy()
    data["fecha"] = pd.to_datetime(data["fecha"]).dt.date
    branches = _ordered_branches(data["nombre_sucursal"].dropna().unique().tolist())
    dates = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
    labels = _week_label_map(dates)

    pivot = data.pivot_table(index="fecha", columns="nombre_sucursal", values=value_col, aggfunc="sum", fill_value=0)
    monthly_totals = {branch: float(pivot[branch].sum()) if branch in pivot.columns else 0 for branch in branches}
    grand_total = sum(monthly_totals.values())

    html = ["<div class='wally-budget-wrap'>", f"<div class='wally-budget-title'>{escape(title)}</div>", "<table class='wally-budget'>"]
    html.append("<thead><tr><th>Semana</th><th>Fecha</th><th>Dia</th>")
    for branch in branches:
        cls = " class='wally-total-head'" if _short_branch_name(branch) == "ONLINE" else ""
        html.append(f"<th{cls}>{escape(_short_branch_name(branch))}</th>")
    html.append("<th class='wally-total-head'>Total</th></tr></thead><tbody>")

    html.append("<tr class='wally-month-total'><td></td><td></td><td>Total rango</td>")
    for branch in branches:
        html.append(f"<td>{_format_money_plain(monthly_totals[branch])}</td>")
    html.append(f"<td>{_format_money_plain(grand_total)}</td></tr>")

    week_totals = {branch: 0.0 for branch in branches}
    week_grand = 0.0
    current_week_start = None
    alt = False

    for day_value in dates:
        week_start, _ = _week_bounds(day_value)
        if current_week_start is not None and week_start != current_week_start:
            label = labels[current_week_start]
            html.append(f"<tr class='wally-subtotal'><td>{escape(label)}</td><td></td><td>Subtotal</td>")
            for branch in branches:
                html.append(f"<td>{_format_money_plain(week_totals[branch])}</td>")
            html.append(f"<td>{_format_money_plain(week_grand)}</td></tr>")
            week_totals = {branch: 0.0 for branch in branches}
            week_grand = 0.0
        current_week_start = week_start

        is_week_first_row = day_value == week_start or day_value == start_date
        row_cls = []
        if alt:
            row_cls.append("wally-alt")
        if day_value.weekday() == 6:
            row_cls.append("wally-sunday")
        if is_week_first_row:
            row_cls.append("wally-week-start")
        row_class = f" class='{' '.join(row_cls)}'" if row_cls else ""
        week_text = labels[week_start] if is_week_first_row else ""
        row_total = 0.0
        html.append(f"<tr{row_class}><td class='wally-week'>{escape(week_text)}</td><td class='wally-date'>{day_value.strftime('%d/%m/%Y')}</td><td class='wally-day'>{DIAS_ES[day_value.weekday()]}</td>")
        for branch in branches:
            value = float(pivot.loc[day_value, branch]) if day_value in pivot.index and branch in pivot.columns else 0.0
            week_totals[branch] += value
            row_total += value
            html.append(f"<td>{_format_money_plain(value)}</td>")
        week_grand += row_total
        html.append(f"<td>{_format_money_plain(row_total)}</td></tr>")
        alt = not alt

    if current_week_start is not None:
        label = labels[current_week_start]
        html.append(f"<tr class='wally-subtotal'><td>{escape(label)}</td><td></td><td>Subtotal</td>")
        for branch in branches:
            html.append(f"<td>{_format_money_plain(week_totals[branch])}</td>")
        html.append(f"<td>{_format_money_plain(week_grand)}</td></tr>")

    html.append("<tr class='wally-grand-total'><td></td><td></td><td>Total acumulado</td>")
    for branch in branches:
        html.append(f"<td>{_format_money_plain(monthly_totals[branch])}</td>")
    html.append(f"<td>{_format_money_plain(grand_total)}</td></tr>")
    html.append("</tbody></table></div>")
    return "".join(html)


def _branch_compliance(budget: pd.DataFrame, start_date: date, end_date: date) -> pd.DataFrame:
    if budget.empty:
        return pd.DataFrame()
    pto = budget.groupby("nombre_sucursal", as_index=False).agg(
        PptoUnid=("unidades", "sum"),
        PptoVenta=("valor_presupuesto", "sum"),
    )
    try:
        real = _real_sales_by_branch(start_date, end_date)
        real["fecha"] = pd.to_datetime(real["fecha"]).dt.date
        real = real.groupby("nombre_sucursal", as_index=False).agg(
            VentaRealUnid=("unidades_reales", "sum"),
            VentaRealNeta=("venta_real", "sum"),
        )
    except Exception as exc:
        st.warning(f"No se pudo consultar venta real por sucursal: {exc}")
        real = pd.DataFrame(columns=["nombre_sucursal", "VentaRealUnid", "VentaRealNeta"])
    joined = pto.merge(real, on="nombre_sucursal", how="left").fillna(0)
    joined["CumplimientoUnid"] = joined["VentaRealUnid"] / joined["PptoUnid"].replace({0: pd.NA}) * 100
    joined["CumplimientoVenta"] = joined["VentaRealNeta"] / joined["PptoVenta"].replace({0: pd.NA}) * 100
    joined["FaltanteUnid"] = joined["PptoUnid"] - joined["VentaRealUnid"]
    joined["FaltanteVenta"] = joined["PptoVenta"] - joined["VentaRealNeta"]
    joined = joined.rename(columns={"nombre_sucursal": "Sucursal"})
    return joined[["Sucursal", "PptoUnid", "PptoVenta", "VentaRealUnid", "VentaRealNeta", "CumplimientoUnid", "CumplimientoVenta", "FaltanteUnid", "FaltanteVenta"]]


def _inventory_by_branch() -> pd.DataFrame:
    return db.read_sql(
        f"""
        SELECT
            Sucursal AS Sucursal,
            SUM(ISNULL(ExistenciaFisica, 0)) AS Existencia
        FROM {db.VIEW_EXISTENCIA}
        GROUP BY Sucursal
        """
    )


def _summary_by_branch(budget: pd.DataFrame, start_date: date, end_date: date) -> pd.DataFrame:
    branches = _ordered_branches((budget["nombre_sucursal"].dropna().unique().tolist() if not budget.empty else []))
    pto = pd.DataFrame(columns=["Sucursal", "UnidadPto", "PptoQ"])
    if not budget.empty:
        pto = budget.groupby("nombre_sucursal", as_index=False).agg(
            UnidadPto=("unidades", "sum"),
            PptoQ=("valor_presupuesto", "sum"),
        ).rename(columns={"nombre_sucursal": "Sucursal"})
        branches = _ordered_branches(branches + pto["Sucursal"].dropna().unique().tolist())
    try:
        real = _real_sales_by_branch(start_date, end_date).groupby("nombre_sucursal", as_index=False).agg(
            UnidFact=("unidades_reales", "sum"),
            VentaQ=("venta_real", "sum"),
        ).rename(columns={"nombre_sucursal": "Sucursal"})
        branches = _ordered_branches(branches + real["Sucursal"].dropna().unique().tolist())
    except Exception as exc:
        st.warning(f"No se pudo consultar venta real por sucursal: {exc}")
        real = pd.DataFrame(columns=["Sucursal", "UnidFact", "VentaQ"])
    try:
        inv = _inventory_by_branch()
        branches = _ordered_branches(branches + inv["Sucursal"].dropna().unique().tolist())
    except Exception as exc:
        st.warning(f"No se pudo consultar existencia por sucursal: {exc}")
        inv = pd.DataFrame(columns=["Sucursal", "Existencia"])

    base = pd.DataFrame({"Sucursal": branches})
    data = base.merge(inv, on="Sucursal", how="left").merge(real, on="Sucursal", how="left").merge(pto, on="Sucursal", how="left").fillna(0)
    data["%CumpUnid"] = data["UnidFact"] / data["UnidadPto"].replace({0: pd.NA})
    data["%CumpVenta"] = data["VentaQ"] / data["PptoQ"].replace({0: pd.NA})
    data["Faltante Unidades"] = data["UnidadPto"] - data["UnidFact"]
    data["FaltanteVenta"] = data["PptoQ"] - data["VentaQ"]
    data["Orden"] = data["Sucursal"].map(lambda value: BRANCH_ORDER.index(_short_branch_name(value)) if _short_branch_name(value) in BRANCH_ORDER else 999)
    data = data.sort_values(["Orden", "Sucursal"]).drop(columns=["Orden"])
    return data[["Sucursal", "Existencia", "UnidFact", "UnidadPto", "%CumpUnid", "VentaQ", "%CumpVenta", "Faltante Unidades", "FaltanteVenta"]]


def _summary_table_html(df: pd.DataFrame) -> str:
    title = "RESUMEN DE PRESUPUESTO POR SUCURSAL"
    if df.empty:
        return f"<div class='wally-budget-wrap'><div class='wally-budget-title'>{title}</div><p style='padding:12px'>No hay informacion para el rango seleccionado.</p></div>"

    columns = [
        "Sucursal",
        "Existencia",
        "UnidFact",
        "UnidadPto",
        "%CumpUnid",
        "VentaQ",
        "%CumpVenta",
        "Faltante Unidades",
        "FaltanteVenta",
    ]
    header_labels = {
        "Sucursal": "Sucursal",
        "Existencia": "Existencia",
        "UnidFact": "UnidFact",
        "UnidadPto": "UnidadPto",
        "%CumpUnid": "%CumpUnid",
        "VentaQ": "VentaQ",
        "%CumpVenta": "%CumpVenta",
        "Faltante Unidades": "Faltante Unidades",
        "FaltanteVenta": "FaltanteVenta",
    }

    totals = {
        "Sucursal": "Total",
        "Existencia": df["Existencia"].sum(),
        "UnidFact": df["UnidFact"].sum(),
        "UnidadPto": df["UnidadPto"].sum(),
        "VentaQ": df["VentaQ"].sum(),
        "Faltante Unidades": df["Faltante Unidades"].sum(),
        "FaltanteVenta": df["FaltanteVenta"].sum(),
    }
    totals["%CumpUnid"] = totals["UnidFact"] / totals["UnidadPto"] if totals["UnidadPto"] else pd.NA
    totals["%CumpVenta"] = totals["VentaQ"] / totals["PptoQ"] if totals.get("PptoQ") else (totals["VentaQ"] / (totals["VentaQ"] + totals["FaltanteVenta"]) if (totals["VentaQ"] + totals["FaltanteVenta"]) else pd.NA)

    def cell(column: str, value) -> str:
        if pd.isna(value):
            text = ""
        elif column in {"VentaQ", "FaltanteVenta"}:
            text = money(value)
        elif column in {"%CumpUnid", "%CumpVenta"}:
            text = f"{float(value) * 100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
        elif column == "Sucursal":
            text = _short_branch_name(value)
        else:
            text = number(value, 0)
        align = " style='text-align:left;'" if column == "Sucursal" else ""
        return f"<td{align}>{escape(str(text))}</td>"

    html = ["<div class='wally-budget-wrap'>", f"<div class='wally-budget-title'>{title}</div>", "<table class='wally-budget'>"]
    html.append("<thead><tr>")
    for column in columns:
        cls = " class='wally-total-head'" if column in {"%CumpUnid", "%CumpVenta", "FaltanteVenta"} else ""
        html.append(f"<th{cls}>{escape(header_labels[column])}</th>")
    html.append("</tr></thead><tbody>")
    for idx, (_, row) in enumerate(df.iterrows()):
        row_class = " class='wally-alt'" if idx % 2 else ""
        html.append(f"<tr{row_class}>")
        for column in columns:
            html.append(cell(column, row[column]))
        html.append("</tr>")
    html.append("<tr class='wally-summary-total'>")
    for column in columns:
        html.append(cell(column, totals.get(column, "")))
    html.append("</tr></tbody></table></div>")
    return "".join(html)


def _seller_report(budget: pd.DataFrame, start_date: date, end_date: date, sucursal: str, vendedor: str) -> pd.DataFrame:
    if budget.empty:
        return pd.DataFrame()
    data = budget.copy()
    if sucursal != "Todas":
        data = data[data["nombre_sucursal"] == sucursal]
    if vendedor != "Todos":
        data = data[data["nombre_vendedor"] == vendedor]
    if data.empty:
        return data
    try:
        real = _real_sales_by_seller(start_date, end_date)
        real["fecha"] = pd.to_datetime(real["fecha"]).dt.date.astype(str)
        real["id_vendedor"] = real["id_vendedor"].astype(str)
        real = real.groupby(["fecha", "id_vendedor", "nombre_sucursal"], as_index=False).agg(
            VentaRealUnid=("unidades_reales", "sum"),
            VentaRealNeta=("venta_real", "sum"),
        )
    except Exception as exc:
        st.warning(f"No se pudo consultar venta real por vendedor: {exc}")
        real = pd.DataFrame(columns=["fecha", "id_vendedor", "nombre_sucursal", "VentaRealUnid", "VentaRealNeta"])
    data["fecha"] = pd.to_datetime(data["fecha"]).dt.date.astype(str)
    data["id_vendedor"] = data["id_vendedor"].astype(str)
    joined = data.merge(real, on=["fecha", "id_vendedor", "nombre_sucursal"], how="left").fillna(0)
    joined["CumplimientoVenta"] = joined["VentaRealNeta"] / joined["vr_presupuesto"].replace({0: pd.NA}) * 100
    joined["CumplimientoUnid"] = joined["VentaRealUnid"] / joined["unidades"].replace({0: pd.NA}) * 100
    joined["Faltante"] = joined["vr_presupuesto"] - joined["VentaRealNeta"]
    joined["Fecha"] = pd.to_datetime(joined["fecha"]).dt.strftime("%d/%m/%Y")
    return joined.rename(
        columns={
            "semana_mes": "Semana",
            "dia_semana": "Dia",
            "id_vendedor": "ID Vendedor",
            "nombre_vendedor": "Vendedor",
            "nombre_sucursal": "Sucursal",
            "unidades": "Ppto Unid",
            "vr_presupuesto": "Ppto Venta",
        }
    )[["Semana", "Fecha", "Dia", "ID Vendedor", "Vendedor", "Sucursal", "Ppto Unid", "Ppto Venta", "VentaRealUnid", "VentaRealNeta", "CumplimientoUnid", "CumplimientoVenta", "Faltante"]]


def _format_report_table(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    for col in data.columns:
        lower = col.lower()
        if lower in {"cumplimientounid", "cumplimientoventa", "%cumpunid", "%cumpventa"}:
            data[col] = data[col].map(lambda x: "" if pd.isna(x) else f"{float(x) * 100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", "."))
        elif any(token in lower for token in ("venta", "faltante")) or lower in {"ventaq", "pptoq"}:
            data[col] = data[col].map(lambda x: money(x) if pd.notna(x) and x != "" else "")
        elif any(token in lower for token in ("unid", "ppto")) and pd.api.types.is_numeric_dtype(data[col]):
            data[col] = data[col].map(lambda x: number(x, 0))
    return data


def _date_controls() -> tuple[date, date]:
    today = date.today()
    default_start = today.replace(day=1)
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        start_date = st.date_input("Fecha inicial", value=default_start, key="pto_fecha_inicio")
    with col2:
        end_date = st.date_input("Fecha final", value=today, key="pto_fecha_fin")
    with col3:
        st.write("")
        st.write("")
        if st.button("Consultar presupuesto", key="pto_consultar"):
            st.rerun()
    if start_date > end_date:
        st.error("La fecha inicial no puede ser mayor que la fecha final.")
    return start_date, end_date


def _import_tab(kind: str) -> None:
    if kind == "branch":
        required = BRANCH_REQUIRED
        numeric_cols = ["unidades", "valorPresupuesto"]
        key_cols = ["codigoSucursal", "fecha"]
        code = get_code("presupuesto", "import_branch")
        title = "Importar presupuesto por sucursal"
    elif kind == "seller":
        required = SELLER_REQUIRED
        upload_required = SELLER_UPLOAD_COLUMNS
        numeric_cols = ["unidades", "vrPresupuesto"]
        key_cols = ["idVendedor", "idSucursal", "fecha"]
        code = get_code("presupuesto", "import_seller")
        title = "Importar presupuesto por vendedor"
    else:
        required = LINE_BRANCH_REQUIRED
        upload_required = LINE_BRANCH_UPLOAD_COLUMNS
        numeric_cols = ["unidades", "ventaQ"]
        key_cols = ["fecha", "idLinea", "idSucursal"]
        code = get_code("presupuesto", "import_line_branch")
        title = "Importar Linea Sucursal"

    section_title(title)
    uploaded = st.file_uploader("Archivo Excel", type=["xlsx", "xls"], key=f"pto_upload_{kind}")
    overwrite = st.checkbox("Sobrescribir registros existentes", value=True, key=f"pto_overwrite_{kind}")
    if not uploaded:
        if kind in {"seller", "line_branch"}:
            st.caption("Columnas obligatorias en este orden: " + ", ".join(upload_required))
        else:
            st.caption("Columnas obligatorias: " + ", ".join(required))
        code_footer(*code)
        return

    try:
        raw = pd.read_excel(uploaded)
    except Exception as exc:
        st.error(f"No se pudo leer el archivo: {exc}")
        code_footer(*code)
        return

    if kind == "seller":
        valid, errors = _validate_seller_budget_frame(raw)
    elif kind == "line_branch":
        valid, errors = _validate_line_branch_budget_frame(raw)
    else:
        valid, errors = _validate_budget_frame(raw, required, numeric_cols, key_cols)
    c1, c2, c3 = st.columns(3)
    c1.metric("Filas leidas", len(raw))
    c2.metric("Filas validas", len(valid))
    c3.metric("Filas con error", len(errors))
    if not valid.empty:
        st.caption("Vista previa de filas validas")
        st.dataframe(valid.head(50), use_container_width=True, hide_index=True)
    if not errors.empty:
        st.caption("Errores detectados")
        st.dataframe(errors, use_container_width=True, hide_index=True)
    if st.button("Confirmar carga", key=f"pto_confirm_{kind}", disabled=valid.empty):
        if kind == "branch":
            inserted, updated, write_errors = _upsert_branch_budget(valid, overwrite)
            tipo = "SUCURSAL"
        elif kind == "seller":
            inserted, updated, write_errors = _upsert_seller_budget(valid, overwrite)
            tipo = "VENDEDOR"
        else:
            inserted, updated, write_errors = _upsert_line_branch_budget(valid, overwrite)
            tipo = "LINEA_SUCURSAL"
        all_errors = pd.concat([errors, write_errors], ignore_index=True) if not write_errors.empty else errors
        _log_import(tipo, uploaded.name, len(raw), inserted, updated, all_errors)
        st.success(f"Carga finalizada. Insertadas: {inserted}. Actualizadas: {updated}. Errores: {len(all_errors)}.")
    code_footer(*code)


def render_import_admin() -> None:
    _budget_css()
    section_title("Administracion de presupuesto")
    st.caption("Carga presupuestos desde Excel. Esta seccion queda en Configuracion para separar ingreso de datos y consulta gerencial.")
    tab_branch, tab_seller, tab_line_branch = st.tabs(["Importar Sucursal", "Importar Vendedor", "Importar Linea Sucursal"])
    with tab_branch:
        _import_tab("branch")
    with tab_seller:
        _import_tab("seller")
    with tab_line_branch:
        _import_tab("line_branch")


def render() -> None:
    _budget_css()
    code_footer(*get_code("presupuesto", "report"))
    start_date, end_date = _date_controls()

    report_view = st.radio(
        "Vista de presupuesto",
        ["Reporte Sucursal", "Reporte Vendedor"],
        horizontal=True,
        key="pto_report_view",
        label_visibility="collapsed",
    )

    if report_view == "Reporte Sucursal":
        branch_budget = _read_local_table("pto_sucursal", start_date, end_date)
        if not branch_budget.empty:
            branch_budget["fecha"] = pd.to_datetime(branch_budget["fecha"]).dt.date

        summary = _summary_by_branch(branch_budget, start_date, end_date)
        section_title("Resumen de presupuesto por sucursal")
        if summary.empty:
            st.info("No hay informacion para el rango seleccionado.")
        else:
            st.markdown(_summary_table_html(summary), unsafe_allow_html=True)
            formatted_summary = _format_report_table(summary)
            st.download_button(
                "Exportar resumen sucursal",
                dataframe_to_excel_bytes({"Resumen Sucursal": formatted_summary}),
                file_name=export_filename("wally_presupuesto_resumen_sucursal"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        code_footer(*get_code("presupuesto", "branch_summary"))

        st.markdown(
            _branch_matrix_html(branch_budget, start_date, end_date, "valor_presupuesto", "PRESUPUESTO DE SUCURSALES POR DIA"),
            unsafe_allow_html=True,
        )
        matrix_q = _branch_matrix_dataframe(branch_budget, start_date, end_date, "valor_presupuesto")
        if not matrix_q.empty:
            st.download_button(
                "Exportar presupuesto sucursal Q",
                dataframe_to_excel_bytes({"Presupuesto Q": matrix_q}),
                file_name=export_filename("wally_presupuesto_sucursal_q"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        code_footer(*get_code("presupuesto", "branch_matrix"))

        st.markdown(
            _branch_matrix_html(branch_budget, start_date, end_date, "unidades", "PRESUPUESTO DE SUCURSALES POR DIA EN UNIDADES"),
            unsafe_allow_html=True,
        )
        matrix_units = _branch_matrix_dataframe(branch_budget, start_date, end_date, "unidades")
        if not matrix_units.empty:
            st.download_button(
                "Exportar presupuesto sucursal unidades",
                dataframe_to_excel_bytes({"Presupuesto Unidades": matrix_units}),
                file_name=export_filename("wally_presupuesto_sucursal_unidades"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        code_footer(*get_code("presupuesto", "branch_units_matrix"))

    if report_view == "Reporte Vendedor":
        seller_budget = _read_local_table("pto_vendedor", start_date, end_date)
        sucursales = ["Todas"] + sorted(seller_budget["nombre_sucursal"].dropna().unique().tolist()) if not seller_budget.empty else ["Todas"]
        vendedores = ["Todos"] + sorted(seller_budget["nombre_vendedor"].dropna().unique().tolist()) if not seller_budget.empty else ["Todos"]
        f1, f2 = st.columns(2)
        with f1:
            sucursal = st.selectbox("Sucursal", sucursales, key="pto_filter_sucursal")
        with f2:
            vendedor = st.selectbox("Vendedor", vendedores, key="pto_filter_vendedor")
        seller_report = _seller_report(seller_budget, start_date, end_date, sucursal, vendedor)
        section_title("Presupuesto y cumplimiento por vendedor")
        if seller_report.empty:
            st.info("No hay presupuesto por vendedor para los filtros seleccionados.")
        else:
            formatted = _format_report_table(seller_report)
            display_table(formatted, height=520, show_total=False)
            st.download_button(
                "Exportar reporte vendedor",
                dataframe_to_excel_bytes({"Cumplimiento Vendedor": formatted}),
                file_name=export_filename("wally_presupuesto_vendedor"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        code_footer(*get_code("presupuesto", "seller_table"))
