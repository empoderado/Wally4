from __future__ import annotations

from datetime import date, timedelta
from html import escape

import pandas as pd
import streamlit as st

from services import db
from services.catalog import get_code
from services.exports import dataframe_to_excel_bytes, export_filename
from services.filters import optional_multiselect
from services.formatting import money, number
from services.local_store import connect
from services.ui import code_footer, metric_card, page_title, section_title


REPORT_COLUMNS = [
    "Unidades",
    "VentaQ",
    "Facturas",
    "TicketPromedio",
    "UPT",
    "VrUnidadPromedio",
    "PorcMargen",
    "PptoUnidades",
    "PptoVenta",
    "CumplimientoUnidades",
    "CumplimientoVenta",
]


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _date_filters() -> tuple[date, date]:
    today = date.today()
    try:
        min_date, max_date = db.min_max_date()
    except Exception:
        min_date = today - timedelta(days=365)
        max_date = today
    min_date = min(min_date, today)
    max_date = max(max_date, today)
    st.sidebar.markdown("### Filtros")
    start_date = st.sidebar.date_input("Fecha Inicio", value=today, min_value=min_date, max_value=max_date, key="asesores_fecha_inicio")
    end_date = st.sidebar.date_input("Fecha Fin", value=today, min_value=min_date, max_value=max_date, key="asesores_fecha_fin")
    if start_date > end_date:
        st.sidebar.error("La fecha inicio no puede ser mayor que la fecha fin.")
        return end_date, start_date
    return start_date, end_date


def _where_filters(sucursales: list[str], vendedores: list[str]) -> str:
    clauses = ["Trn = 'FV'"]
    if sucursales:
        clauses.append(f"Sucursal IN ({db.sql_literal_list(sucursales)})")
    if vendedores:
        clauses.append(f"Vendedor IN ({db.sql_literal_list(vendedores)})")
    return " AND ".join(clauses)


def _normalize_branch(value: object) -> str:
    text = str(value or "").strip().upper()
    replacements = {
        "PARQUE LAS AMERICAS": "AMERICAS",
        "PARQUE LAS AMÉRICAS": "AMERICAS",
        "ON-LINE": "ONLINE",
        "NARANJO": "NARANJO MALL",
    }
    return replacements.get(text, text)


def _advisor_code(value: object) -> str:
    text = str(value or "").strip()
    digits = "".join(char for char in text if char.isdigit())
    if digits:
        return digits[-3:].zfill(3)
    return text[-3:].rjust(3, "0")


def _advisor_label(id_vendedor: object, asesor: object) -> str:
    name = str(asesor or "").strip()
    if not name.lower().startswith("subtotal"):
        return f"{_advisor_code(id_vendedor)} - {name}" if name else _advisor_code(id_vendedor)
    return name


def _read_sales(start_date: date, end_date: date, sucursales: list[str], vendedores: list[str]) -> pd.DataFrame:
    start, end = db.date_params(start_date, end_date)
    where_extra = _where_filters(sucursales, vendedores)
    return db.read_sql(
        f"""
        SELECT
            Sucursal,
            CAST(IdVendedor AS varchar(50)) AS IdVendedor,
            Vendedor AS Asesor,
            SUM(ISNULL(Unidades, 0)) AS Unidades,
            SUM(ISNULL(VentaNetaQ, 0)) AS VentaQ,
            COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END) AS Facturas,
            SUM(ISNULL(VentaNetaQ, 0)) - SUM(ISNULL(CostoTotal, 0)) AS MargenQ
        FROM {db.VIEW_VENTAS}
        WHERE CAST(Fecha AS date) BETWEEN ? AND ?
          AND {where_extra}
        GROUP BY Sucursal, CAST(IdVendedor AS varchar(50)), Vendedor
        ORDER BY Sucursal, VentaQ DESC
        """,
        (start, end),
    )


def _read_budget(start_date: date, end_date: date, sucursales: list[str], vendedores: list[str]) -> pd.DataFrame:
    query = """
        SELECT
            id_vendedor AS IdVendedor,
            nombre_vendedor AS Asesor,
            nombre_sucursal AS Sucursal,
            SUM(unidades) AS PptoUnidades,
            SUM(vr_presupuesto) AS PptoVenta
        FROM pto_vendedor
        WHERE fecha BETWEEN ? AND ?
    """
    params: list[str] = [start_date.isoformat(), end_date.isoformat()]
    if vendedores:
        query += f" AND nombre_vendedor IN ({','.join(['?'] * len(vendedores))})"
        params.extend(vendedores)
    query += """
        GROUP BY id_vendedor, nombre_vendedor, nombre_sucursal
    """
    conn = connect()
    try:
        budget = pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()
    if sucursales and not budget.empty:
        selected = {_normalize_branch(branch) for branch in sucursales}
        budget = budget[budget["Sucursal"].map(_normalize_branch).isin(selected)].reset_index(drop=True)
    return budget


def _normalize_frame(data: pd.DataFrame, columns: dict[str, object]) -> pd.DataFrame:
    frame = data.copy()
    for column, default in columns.items():
        if column not in frame.columns:
            frame[column] = default
    return frame


def _build_block(start_date: date, end_date: date, sucursales: list[str], vendedores: list[str]) -> pd.DataFrame:
    sales = _normalize_frame(
        _read_sales(start_date, end_date, sucursales, vendedores),
        {"Sucursal": "", "IdVendedor": "", "Asesor": "", "Unidades": 0, "VentaQ": 0, "Facturas": 0, "MargenQ": 0},
    )
    budget = _normalize_frame(
        _read_budget(start_date, end_date, sucursales, vendedores),
        {"Sucursal": "", "IdVendedor": "", "Asesor": "", "PptoUnidades": 0, "PptoVenta": 0},
    )
    for frame in (sales, budget):
        frame["Sucursal"] = frame["Sucursal"].fillna("").astype(str).str.strip()
        frame["SucursalKey"] = frame["Sucursal"].map(_normalize_branch)
        frame["IdVendedor"] = frame["IdVendedor"].fillna("").astype(str).str.strip()
        frame["Asesor"] = frame["Asesor"].fillna("").astype(str).str.strip()

    data = sales.merge(budget, on=["SucursalKey", "IdVendedor"], how="outer", suffixes=("_Venta", "_Ppto"))
    data["Sucursal"] = data.get("Sucursal_Venta", "").fillna("").astype(str).str.strip()
    budget_branch = data.get("Sucursal_Ppto", "").fillna("").astype(str).str.strip()
    data["Sucursal"] = data["Sucursal"].mask(data["Sucursal"].eq(""), budget_branch)
    data["Asesor"] = data.get("Asesor_Venta", "").fillna("").astype(str).str.strip()
    budget_advisor = data.get("Asesor_Ppto", "").fillna("").astype(str).str.strip()
    data["Asesor"] = data["Asesor"].mask(data["Asesor"].eq(""), budget_advisor)
    data = data.drop(columns=[col for col in ["Sucursal_Venta", "Sucursal_Ppto", "SucursalKey", "Asesor_Venta", "Asesor_Ppto"] if col in data.columns])
    for column in ["Unidades", "VentaQ", "Facturas", "MargenQ", "PptoUnidades", "PptoVenta"]:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0)
    for column in ["Sucursal", "IdVendedor", "Asesor"]:
        data[column] = data[column].fillna("").astype(str).str.strip()
    data["Asesor"] = data.apply(lambda row: _advisor_label(row["IdVendedor"], row["Asesor"]), axis=1)
    return _add_calculated_columns(data)


def _add_calculated_columns(data: pd.DataFrame) -> pd.DataFrame:
    frame = data.copy()
    frame["TicketPromedio"] = frame["VentaQ"] / frame["Facturas"].replace({0: pd.NA})
    frame["UPT"] = frame["Unidades"] / frame["Facturas"].replace({0: pd.NA})
    frame["VrUnidadPromedio"] = frame["VentaQ"] / frame["Unidades"].replace({0: pd.NA})
    frame["PorcMargen"] = frame["MargenQ"] / frame["VentaQ"].replace({0: pd.NA})
    frame["CumplimientoUnidades"] = frame["Unidades"] / frame["PptoUnidades"].replace({0: pd.NA})
    frame["CumplimientoVenta"] = frame["VentaQ"] / frame["PptoVenta"].replace({0: pd.NA})
    for column in [
        "TicketPromedio",
        "UPT",
        "VrUnidadPromedio",
        "PorcMargen",
        "CumplimientoUnidades",
        "CumplimientoVenta",
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    return frame


def _subtotal_row(group: pd.DataFrame, branch: str) -> pd.Series:
    totals = {
        "Sucursal": branch,
        "IdVendedor": "",
        "Asesor": f"SubTotal {branch}",
        "Unidades": group["Unidades"].sum(),
        "VentaQ": group["VentaQ"].sum(),
        "Facturas": group["Facturas"].sum(),
        "MargenQ": group["MargenQ"].sum(),
        "PptoUnidades": group["PptoUnidades"].sum(),
        "PptoVenta": group["PptoVenta"].sum(),
        "EsSubtotal": True,
    }
    return _add_calculated_columns(pd.DataFrame([totals])).iloc[0]


def _with_subtotals(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return data
    rows: list[pd.Series] = []
    branch_order = (
        data.groupby("Sucursal", dropna=False, as_index=False)["VentaQ"]
        .sum()
        .sort_values(["VentaQ", "Sucursal"], ascending=[False, True])["Sucursal"]
        .astype(str)
        .tolist()
    )
    data = data.copy()
    data["_BranchOrder"] = data["Sucursal"].astype(str).map({branch: idx for idx, branch in enumerate(branch_order)})
    sorted_data = data.sort_values(["_BranchOrder", "VentaQ", "Asesor"], ascending=[True, False, True]).drop(columns=["_BranchOrder"]).reset_index(drop=True)
    for branch, group in sorted_data.groupby("Sucursal", dropna=False, sort=False):
        branch_group = group.copy()
        branch_group["EsSubtotal"] = False
        rows.extend([row for _, row in branch_group.iterrows()])
        rows.append(_subtotal_row(branch_group, str(branch)))
    return pd.DataFrame(rows).reset_index(drop=True)


def _format_pct(value) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value) * 100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def _format_cell(column: str, value) -> str:
    if pd.isna(value) or value == "":
        return ""
    if column in {"VentaQ", "TicketPromedio", "VrUnidadPromedio", "PptoVenta"}:
        return money(value)
    if column in {"PorcMargen", "CumplimientoUnidades", "CumplimientoVenta"}:
        return _format_pct(value)
    if column == "UPT":
        return number(value, 2)
    return number(value, 0)


def _cell(block: pd.DataFrame, branch: str, advisor: str, is_subtotal: bool, column: str) -> str:
    if block.empty:
        return ""
    mask = (block["Sucursal"].astype(str) == branch) & (block["Asesor"].astype(str) == advisor) & (block["EsSubtotal"].astype(bool) == is_subtotal)
    found = block.loc[mask]
    if found.empty:
        return ""
    return _format_cell(column, found.iloc[0].get(column, ""))


def _report_css() -> None:
    st.markdown(
        """
        <style>
        .wally-advisors-wrap {
            width: 100%;
            overflow-x: auto;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            background: #ffffff;
            box-shadow: 0 2px 10px rgba(15, 23, 42, .04);
        }
        table.wally-advisors {
            border-collapse: collapse;
            width: max-content;
            min-width: 100%;
            font-size: 12px;
        }
        table.wally-advisors th,
        table.wally-advisors td {
            border: 1px solid #cbd5e1;
            padding: 5px 7px;
            white-space: nowrap;
        }
        table.wally-advisors th {
            background: #ffffff;
            color: #b91c1c;
            font-weight: 850;
            text-transform: uppercase;
            text-align: center;
        }
        table.wally-advisors th.wally-period {
            background: #eef2ff;
            color: #111827;
            font-size: 13px;
        }
        table.wally-advisors th.wally-period-accumulated {
            background: #dcfce7;
            color: #14532d;
        }
        table.wally-advisors th.wally-section {
            background: #f8fafc;
            color: #b91c1c;
        }
        table.wally-advisors td {
            text-align: right;
            color: #0f172a;
        }
        table.wally-advisors td.wally-branch,
        table.wally-advisors td.wally-advisor {
            text-align: left;
        }
        table.wally-advisors tr.wally-alt td {
            background: #f8fafc;
        }
        table.wally-advisors tr.wally-subtotal td {
            background: #e0f2fe;
            color: #0f172a;
            font-weight: 850;
            border-top: 2px solid #334155;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _row_order(daily_rows: pd.DataFrame, accumulated_rows: pd.DataFrame) -> pd.DataFrame:
    source = accumulated_rows if not accumulated_rows.empty else daily_rows
    ordered = source[["Sucursal", "Asesor", "EsSubtotal"]].drop_duplicates().reset_index(drop=True)
    if not daily_rows.empty:
        ordered = pd.concat([ordered, daily_rows[["Sucursal", "Asesor", "EsSubtotal"]]], ignore_index=True).drop_duplicates().reset_index(drop=True)
    return ordered


def _render_report_table(daily: pd.DataFrame, accumulated: pd.DataFrame, start_date: date, end_date: date) -> str:
    daily_rows = _with_subtotals(daily)
    accumulated_rows = _with_subtotals(accumulated)
    identity = _row_order(daily_rows, accumulated_rows)
    if identity.empty:
        return "<div class='wally-advisors-wrap'><p style='padding:12px'>No hay datos para la fecha seleccionada.</p></div>"

    labels = {
        "Unidades": "Unidades",
        "VentaQ": "VentaQ",
        "Facturas": "Facturas",
        "TicketPromedio": "Ticket Promedio",
        "UPT": "UPT",
        "VrUnidadPromedio": "Vr Unidad Promedio",
        "PorcMargen": "% Margen",
        "PptoUnidades": "Unidades",
        "PptoVenta": "Venta",
        "CumplimientoUnidades": "% Unidades",
        "CumplimientoVenta": "% Venta",
    }

    html = ["<div class='wally-advisors-wrap'><table class='wally-advisors'>"]
    html.append("<thead>")
    daily_label = start_date.strftime("%d/%m/%Y") if start_date == end_date else f"{start_date.strftime('%d/%m/%Y')} al {end_date.strftime('%d/%m/%Y')}"
    html.append(
        "<tr><th rowspan='3'>Sucursal</th><th rowspan='3'>Asesor</th>"
        f"<th class='wally-period' colspan='11'>Diario - {daily_label}</th>"
        f"<th class='wally-period wally-period-accumulated' colspan='11'>Acumulado - {_month_start(end_date).strftime('%d/%m/%Y')} al {end_date.strftime('%d/%m/%Y')}</th></tr>"
    )
    html.append(
        "<tr>"
        "<th class='wally-section' colspan='3'>Ventas</th><th class='wally-section' colspan='3'>KPIS</th><th class='wally-section'>Margen</th><th class='wally-section' colspan='2'>Presupuesto</th><th class='wally-section' colspan='2'>Cumplimiento</th>"
        "<th class='wally-section' colspan='3'>Ventas</th><th class='wally-section' colspan='3'>KPIS</th><th class='wally-section'>Margen</th><th class='wally-section' colspan='2'>Presupuesto</th><th class='wally-section' colspan='2'>Cumplimiento</th>"
        "</tr>"
    )
    html.append("<tr>")
    for _ in range(2):
        for column in REPORT_COLUMNS:
            html.append(f"<th>{escape(labels[column])}</th>")
    html.append("</tr></thead><tbody>")

    previous_branch = None
    alt = False
    for _, row in identity.iterrows():
        branch = str(row["Sucursal"])
        advisor = str(row["Asesor"])
        is_subtotal = bool(row["EsSubtotal"])
        row_class = "wally-subtotal" if is_subtotal else ("wally-alt" if alt else "")
        html.append(f"<tr class='{row_class}'>")
        branch_label = branch if previous_branch != branch or is_subtotal else ""
        html.append(f"<td class='wally-branch'>{escape(branch_label)}</td><td class='wally-advisor'>{escape(advisor)}</td>")
        for block in (daily_rows, accumulated_rows):
            for column in REPORT_COLUMNS:
                html.append(f"<td>{escape(_cell(block, branch, advisor, is_subtotal, column))}</td>")
        html.append("</tr>")
        previous_branch = branch
        if not is_subtotal:
            alt = not alt
    html.append("</tbody></table></div>")
    return "".join(html)


def _export_frame(block: pd.DataFrame, label: str) -> pd.DataFrame:
    data = _with_subtotals(block)
    if data.empty:
        return data
    data = data.copy()
    data.insert(0, "Periodo", label)
    return data[
        [
            "Periodo",
            "Sucursal",
            "Asesor",
            "Unidades",
            "VentaQ",
            "Facturas",
            "TicketPromedio",
            "UPT",
            "VrUnidadPromedio",
            "PorcMargen",
            "PptoUnidades",
            "PptoVenta",
            "CumplimientoUnidades",
            "CumplimientoVenta",
        ]
    ]


def render() -> None:
    _report_css()
    page_title("Asesores", "Reporte diario y acumulado por sucursal y asesor")
    code_footer(*get_code("asesores", "report"))
    start_date, end_date = _date_filters()
    month_start = _month_start(end_date)
    try:
        sucursales = optional_multiselect("Sucursal", db.distinct_values(db.VIEW_VENTAS, "Sucursal"))
        vendedores = optional_multiselect("Asesor", db.distinct_values(db.VIEW_VENTAS, "Vendedor"))
    except Exception as exc:
        st.error("No se pudieron cargar filtros de asesores.")
        st.exception(exc)
        return

    try:
        with st.spinner("Cargando reporte de asesores..."):
            daily = _build_block(start_date, end_date, sucursales, vendedores)
            accumulated = _build_block(month_start, end_date, sucursales, vendedores)
    except Exception as exc:
        st.error("No se pudo generar el reporte Asesores.")
        st.exception(exc)
        return

    total_daily = daily.sum(numeric_only=True)
    total_accumulated = accumulated.sum(numeric_only=True)
    cols = st.columns(6)
    with cols[0]:
        metric_card("Venta Rango", money(total_daily.get("VentaQ", 0)))
    with cols[1]:
        metric_card("Unidades Rango", number(total_daily.get("Unidades", 0), 0))
    with cols[2]:
        metric_card("Facturas Rango", number(total_daily.get("Facturas", 0), 0))
    with cols[3]:
        metric_card("Venta Acum.", money(total_accumulated.get("VentaQ", 0)))
    with cols[4]:
        metric_card("Unidades Acum.", number(total_accumulated.get("Unidades", 0), 0))
    with cols[5]:
        cumplimiento = (total_accumulated.get("VentaQ", 0) / total_accumulated.get("PptoVenta", 0)) if total_accumulated.get("PptoVenta", 0) else 0
        metric_card("Cumpl. Venta Acum.", f"{cumplimiento * 100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", "."))

    section_title("Reporte de Asesores")
    if float(total_accumulated.get("PptoVenta", 0) or 0) == 0 and float(total_accumulated.get("PptoUnidades", 0) or 0) == 0:
        st.info("No hay presupuesto por asesor cargado para el periodo acumulado seleccionado.")
    st.markdown(_render_report_table(daily, accumulated, start_date, end_date), unsafe_allow_html=True)
    code_footer(*get_code("asesores", "detail_table"))

    export_daily = _export_frame(daily, "Diario")
    export_accumulated = _export_frame(accumulated, "Acumulado")
    st.download_button(
        "Exportar asesores a Excel",
        dataframe_to_excel_bytes({"Diario": export_daily, "Acumulado": export_accumulated}),
        file_name=export_filename("wally_asesores"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
