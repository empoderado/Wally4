from __future__ import annotations

from datetime import date, timedelta
from html import escape

import pandas as pd
import streamlit as st

from services import db
from services.branches import filter_frame
from services.catalog import get_code
from services.exports import dataframe_to_excel_bytes, export_filename
from services.filters import optional_multiselect
from services.formatting import money, number, percent
from services.local_store import connect
from services.ui import code_footer, metric_card, page_title, section_title


REPORT_COLUMNS = [
    "VentaPrevQ",
    "UPTPrev",
    "VentaQ",
    "PptoVenta",
    "Pendiente",
    "CumplimientoVenta",
    "Facturas",
    "TicketPromedio",
    "UPT",
    "VrUnidadPromedio",
]


def _previous_month_range(ref_date: date) -> tuple[date, date]:
    first_day_curr = ref_date.replace(day=1)
    last_day_prev = first_day_curr - timedelta(days=1)
    first_day_prev = last_day_prev.replace(day=1)
    return first_day_prev, last_day_prev


def _date_filters() -> tuple[date, date]:
    today = date.today()
    first_day_curr = today.replace(day=1)
    try:
        min_date, max_date = db.min_max_date()
    except Exception:
        min_date = today - timedelta(days=365)
        max_date = today
    min_date = min(min_date, first_day_curr)
    max_date = max(max_date, today)
    st.sidebar.markdown("### Filtros")
    start_date = st.sidebar.date_input("Fecha Inicio", value=first_day_curr, min_value=min_date, max_value=max_date, key="ger_asesores_fecha_inicio")
    end_date = st.sidebar.date_input("Fecha Fin", value=today, min_value=min_date, max_value=max_date, key="ger_asesores_fecha_fin")
    if start_date > end_date:
        st.sidebar.error("La fecha inicio no puede ser mayor que la fecha fin.")
        return end_date, start_date
    return start_date, end_date


def _where_filters(sucursales: list[str], vendedores: list[str]) -> str:
    clauses = ["1=1"]
    if sucursales:
        clauses.append(f"Sucursal IN ({db.sql_literal_list(sucursales)})")
    if vendedores:
        clauses.append(f"Vendedor IN ({db.sql_literal_list(vendedores)})")
    return " AND ".join(clauses)


def _normalize_branch(value: object) -> str:
    text = str(value or "").strip().upper()
    replacements = {
        "PARQUE LAS AMERICAS": "LAS AMERICAS",
        "PARQUE LAS AMÉRICAS": "LAS AMERICAS",
        "AMERICAS": "LAS AMERICAS",
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


def _get_vendedor_meta(id_vendedor: str, nombre: str, meta_map: dict) -> tuple[str, str, str]:
    try:
        val = int("".join(c for c in str(id_vendedor) if c.isdigit()))
    except ValueError:
        val = None

    if val is not None and val in meta_map:
        return meta_map[val]

    # Fallback to hardcoded logic if not found
    name_lower = nombre.lower()
    if "caja" in name_lower or "cajero" in name_lower:
        cargo = "Cajero"
    elif "sup" in name_lower or "supervisor" in name_lower:
        cargo = "Supervisor"
    elif "coordinador" in name_lower:
        cargo = "Coordinador"
    else:
        cargo = "Asesor de Ventas"
        
    try:
        val_mod = int("".join(c for c in id_vendedor if c.isdigit()))
        if val_mod % 3 == 0:
            turno = "Mañana"
        elif val_mod % 3 == 1:
            turno = "Tarde"
        else:
            turno = "Completo"
    except ValueError:
        turno = "Completo"
        
    return turno, cargo, "Activo"


def _read_sales_current(start_date: date, end_date: date, sucursales: list[str], vendedores: list[str]) -> pd.DataFrame:
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
            SUM(CASE WHEN Trn = 'FV' THEN ISNULL(Unidades, 0) ELSE 0 END) AS UnidadesUPT,
            COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END) AS Facturas
        FROM {db.VIEW_VENTAS}
        WHERE Fecha >= ? AND Fecha < DATEADD(day, 1, ?)
          AND {where_extra}
        GROUP BY Sucursal, CAST(IdVendedor AS varchar(50)), Vendedor
        ORDER BY Sucursal, VentaQ DESC
        """,
        (start, end),
    )


def _read_sales_prev_month(prev_start: date, prev_end: date, sucursales: list[str], vendedores: list[str]) -> pd.DataFrame:
    start, end = db.date_params(prev_start, prev_end)
    where_extra = _where_filters(sucursales, vendedores)
    return db.read_sql(
        f"""
        SELECT
            Sucursal,
            CAST(IdVendedor AS varchar(50)) AS IdVendedor,
            Vendedor AS Asesor,
            SUM(ISNULL(Unidades, 0)) AS Unidades_Prev,
            SUM(ISNULL(VentaNetaQ, 0)) AS VentaQ_Prev,
            SUM(CASE WHEN Trn = 'FV' THEN ISNULL(Unidades, 0) ELSE 0 END) AS UnidadesUPT_Prev,
            COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END) AS Facturas_Prev
        FROM {db.VIEW_VENTAS}
        WHERE Fecha >= ? AND Fecha < DATEADD(day, 1, ?)
          AND {where_extra}
        GROUP BY Sucursal, CAST(IdVendedor AS varchar(50)), Vendedor
        """,
        (start, end),
    )


def _read_budget(start_date: date, end_date: date, sucursales: list[str], vendedores: list[str]) -> pd.DataFrame:
    query = """
        SELECT
            id_vendedor AS IdVendedor,
            nombre_vendedor AS Asesor,
            nombre_sucursal AS Sucursal,
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
    return filter_frame(budget, ["Sucursal"])


def _normalize_frame(data: pd.DataFrame, columns: dict[str, object]) -> pd.DataFrame:
    frame = data.copy()
    for column, default in columns.items():
        if column not in frame.columns:
            frame[column] = default
    return frame


def _build_block(start_date: date, end_date: date, sucursales: list[str], vendedores: list[str]) -> pd.DataFrame:
    sales_curr = _normalize_frame(
        _read_sales_current(start_date, end_date, sucursales, vendedores),
        {"Sucursal": "", "IdVendedor": "", "Asesor": "", "Unidades": 0, "VentaQ": 0, "UnidadesUPT": 0, "Facturas": 0},
    )
    
    prev_start, prev_end = _previous_month_range(end_date)
    sales_prev = _normalize_frame(
        _read_sales_prev_month(prev_start, prev_end, sucursales, vendedores),
        {"Sucursal": "", "IdVendedor": "", "Asesor": "", "Unidades_Prev": 0, "VentaQ_Prev": 0, "UnidadesUPT_Prev": 0, "Facturas_Prev": 0},
    )
    
    budget = _normalize_frame(
        _read_budget(start_date, end_date, sucursales, vendedores),
        {"Sucursal": "", "IdVendedor": "", "Asesor": "", "PptoVenta": 0},
    )
    
    for frame in (sales_curr, sales_prev, budget):
        frame["Sucursal"] = frame["Sucursal"].fillna("").astype(str).str.strip()
        frame["SucursalKey"] = frame["Sucursal"].map(_normalize_branch)
        frame["IdVendedor"] = frame["IdVendedor"].fillna("").astype(str).str.strip()
        frame["Asesor"] = frame["Asesor"].fillna("").astype(str).str.strip()

    # Outer merge
    data = sales_curr.merge(budget, on=["SucursalKey", "IdVendedor"], how="outer", suffixes=("_Venta", "_Ppto"))
    data = data.merge(sales_prev, on=["SucursalKey", "IdVendedor"], how="outer", suffixes=("", "_Prev"))
    
    # Resolve names
    sucursales_cols = [c for c in ["Sucursal_Venta", "Sucursal_Ppto", "Sucursal", "Sucursal_Prev"] if c in data.columns]
    data["Sucursal_Final"] = ""
    for col in sucursales_cols:
        data["Sucursal_Final"] = data["Sucursal_Final"].mask(data["Sucursal_Final"].eq(""), data[col].fillna("").astype(str).str.strip())
        
    asesores_cols = [c for c in ["Asesor_Venta", "Asesor_Ppto", "Asesor", "Asesor_Prev"] if c in data.columns]
    data["Asesor_Final"] = ""
    for col in asesores_cols:
        data["Asesor_Final"] = data["Asesor_Final"].mask(data["Asesor_Final"].eq(""), data[col].fillna("").astype(str).str.strip())
        
    data["Sucursal"] = data["Sucursal_Final"].map(_normalize_branch)
    data["Asesor"] = data["Asesor_Final"]
    
    data = data.drop(columns=[col for col in ["Sucursal_Venta", "Sucursal_Ppto", "Sucursal_Prev", "SucursalKey", "Asesor_Venta", "Asesor_Ppto", "Asesor_Prev", "Sucursal_Final", "Asesor_Final"] if col in data.columns])
    
    numeric_cols = [
        "Unidades", "VentaQ", "UnidadesUPT", "Facturas", "PptoVenta",
        "Unidades_Prev", "VentaQ_Prev", "UnidadesUPT_Prev", "Facturas_Prev"
    ]
    for column in numeric_cols:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0)
        
    for column in ["Sucursal", "IdVendedor", "Asesor"]:
        data[column] = data[column].fillna("").astype(str).str.strip()
        
    # Load vendedor meta mapping from DB (fresh per run, utilizing db query cache)
    try:
        df_meta = db.read_sql("SELECT CODIGO, Cargo, Turno, Activo FROM dbo.VwColaboradoresTurno")
        meta_map = {
            int(row["CODIGO"]): (
                str(row["Turno"]),
                str(row["Cargo"]),
                "Activo" if bool(row["Activo"]) else "Inactivo"
            )
            for _, row in df_meta.iterrows()
        }
    except Exception:
        meta_map = {}

    # Generate Turno, Cargo and Estado
    data["Turno"] = ""
    data["Cargo"] = ""
    data["Estado"] = ""
    t_list = []
    c_list = []
    e_list = []
    for _, row in data.iterrows():
        t, c, e = _get_vendedor_meta(row["IdVendedor"], row["Asesor"], meta_map)
        t_list.append(t)
        c_list.append(c)
        e_list.append(e)
    data["Turno"] = t_list
    data["Cargo"] = c_list
    data["Estado"] = e_list
    
    # Label Asesor with code
    data["Asesor"] = data.apply(lambda row: _advisor_label(row["IdVendedor"], row["Asesor"]), axis=1)
    
    return _add_calculated_columns(data)


def _add_calculated_columns(data: pd.DataFrame) -> pd.DataFrame:
    frame = data.copy()
    frame["VentaPrevQ"] = frame["VentaQ_Prev"]
    frame["UPTPrev"] = frame["UnidadesUPT_Prev"] / frame["Facturas_Prev"].replace({0: pd.NA})
    frame["TicketPromedio"] = frame["VentaQ"] / frame["Facturas"].replace({0: pd.NA})
    frame["UPT"] = frame["UnidadesUPT"] / frame["Facturas"].replace({0: pd.NA})
    frame["VrUnidadPromedio"] = frame["VentaQ"] / frame["Unidades"].replace({0: pd.NA})
    frame["CumplimientoVenta"] = frame["VentaQ"] / frame["PptoVenta"].replace({0: pd.NA})
    frame["Pendiente"] = frame["PptoVenta"] - frame["VentaQ"]
    
    cols = [
        "VentaPrevQ",
        "UPTPrev",
        "TicketPromedio",
        "UPT",
        "VrUnidadPromedio",
        "CumplimientoVenta",
        "Pendiente",
    ]
    for column in cols:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    return frame


def _subtotal_row(group: pd.DataFrame, branch: str) -> pd.Series:
    tot_unidades_prev = group["Unidades_Prev"].sum()
    tot_unidades_upt_prev = group["UnidadesUPT_Prev"].sum()
    tot_facturas_prev = group["Facturas_Prev"].sum()
    tot_unidades = group["Unidades"].sum()
    tot_unidades_upt = group["UnidadesUPT"].sum()
    tot_facturas = group["Facturas"].sum()
    tot_venta = group["VentaQ"].sum()
    tot_venta_prev = group["VentaQ_Prev"].sum()
    tot_ppto = group["PptoVenta"].sum()
    
    totals = {
        "Sucursal": branch,
        "IdVendedor": "",
        "Asesor": f"SubTotal {branch}",
        "Turno": "",
        "Cargo": "",
        "Estado": "",
        "Unidades_Prev": tot_unidades_prev,
        "UnidadesUPT_Prev": tot_unidades_upt_prev,
        "Facturas_Prev": tot_facturas_prev,
        "Unidades": tot_unidades,
        "UnidadesUPT": tot_unidades_upt,
        "Facturas": tot_facturas,
        "VentaQ": tot_venta,
        "VentaQ_Prev": tot_venta_prev,
        "PptoVenta": tot_ppto,
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


def _format_cell(column: str, value) -> str:
    if pd.isna(value) or value == "":
        return ""
    if column in {"VentaPrevQ", "VentaQ", "TicketPromedio", "VrUnidadPromedio", "PptoVenta", "Pendiente"}:
        return money(value)
    if column in {"CumplimientoVenta"}:
        return percent(value)
    if column in {"UPTPrev", "UPT"}:
        return number(value, 2)
    if column == "Facturas":
        return number(value, 0)
    return str(value)


def _cell(block: pd.DataFrame, branch: str, advisor: str, is_subtotal: bool, column: str) -> str:
    if block.empty:
        return ""
    mask = (block["Sucursal"].astype(str) == branch) & (block["Asesor"].astype(str) == advisor) & (block["EsSubtotal"].astype(bool) == is_subtotal)
    found = block.loc[mask]
    if found.empty:
        return ""
    return _format_cell(column, found.iloc[0].get(column, ""))


def _pending_cell(block: pd.DataFrame, branch: str, advisor: str, is_subtotal: bool) -> str:
    if block.empty:
        return "<td></td>"
    mask = (block["Sucursal"].astype(str) == branch) & (block["Asesor"].astype(str) == advisor) & (block["EsSubtotal"].astype(bool) == is_subtotal)
    found = block.loc[mask]
    if found.empty:
        return "<td></td>"
    value = float(found.iloc[0].get("Pendiente", 0) or 0)
    css_class = "wally-pending-positive" if value > 0 else ("wally-pending-negative" if value < 0 else "")
    return f"<td class='{css_class}'>{escape(money(abs(value)))}</td>"


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
            white-space: normal;
            line-height: 1.12;
            vertical-align: middle;
        }
        table.wally-advisors th.wally-period {
            background: #e9d5ff;
            color: #581c87;
            font-size: 13px;
        }
        table.wally-advisors th.wally-th-pendiente {
            color: #000000 !important;
            font-weight: bold !important;
        }
        table.wally-advisors th.wally-period-accumulated {
            background: #dcfce7;
            color: #14532d;
            font-size: 13px;
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
        table.wally-advisors td.wally-advisor,
        table.wally-advisors td.wally-turno,
        table.wally-advisors td.wally-cargo,
        table.wally-advisors td.wally-estado {
            text-align: left;
        }
        table.wally-advisors td.wally-advisor {
            max-width: 32ch;
            white-space: normal;
            overflow-wrap: break-word;
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
        table.wally-advisors td.wally-pending-positive {
            color: #b91c1c !important;
            font-weight: 850;
        }
        table.wally-advisors td.wally-pending-negative {
            color: #15803d !important;
            font-weight: 850;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _column_labels() -> dict[str, str]:
    return {
        "VentaPrevQ": "Venta Neta",
        "UPTPrev": "UPT",
        "VentaQ": "Venta Neta",
        "Facturas": "Facturas",
        "TicketPromedio": "Ticket Prom.",
        "UPT": "UPT",
        "VrUnidadPromedio": "Vr. Unidad Prom.",
        "PptoVenta": "Presupuesto",
        "CumplimientoVenta": "% Cumpl.",
        "Pendiente": "Pendiente",
    }


def _column_width_chars(rows: pd.DataFrame, column: str, label: str) -> int:
    header_width = max((len(part) for part in label.split()), default=len(label))
    if column == "Sucursal":
        values = rows.get("Sucursal", pd.Series(dtype=object)).fillna("").astype(str)
        content_width = max((len(value) for value in values), default=0)
        return int((max(header_width, content_width) + 2) * 0.5)
    if column == "Asesor":
        values = rows.get("Asesor", pd.Series(dtype=object)).fillna("").astype(str)
        content_width = max((len(value) for value in values), default=0)
        return min(32, max(8, header_width, content_width))
    if column in {"Turno", "Cargo", "Estado"}:
        values = rows.get(column, pd.Series(dtype=object)).fillna("").astype(str)
        content_width = max((len(value) for value in values), default=0)
        return int((max(header_width, content_width) + 2) * 0.66)
        
    formatted = rows.get(column, pd.Series(dtype=object)).map(lambda value: _format_cell(column, value))
    return max(5, header_width, max((len(value) for value in formatted), default=0)) + 2


def _table_colgroup(rows: pd.DataFrame, columns: list[str], labels: dict[str, str]) -> str:
    definitions = [
        ("Sucursal", "Sucursal", "wally-col-branch"),
        ("Asesor", "Asesor", "wally-col-advisor"),
        ("Turno", "Turno", "wally-col-turno"),
        ("Cargo", "Cargo", "wally-col-cargo"),
        ("Estado", "Estado", "wally-col-estado"),
        *[(column, labels[column], f"wally-col-{column.lower()}") for column in columns],
    ]
    html = ["<colgroup>"]
    for column, label, css_class in definitions:
        width = _column_width_chars(rows, column, label)
        html.append(
            f"<col class='{css_class}' style='width:{width}ch;min-width:{width}ch;max-width:{width}ch'>"
        )
    html.append("</colgroup>")
    return "".join(html)


def _render_report_table(block: pd.DataFrame, start_date: date, end_date: date, columns: list[str]) -> str:
    rows = _with_subtotals(block)
    if rows.empty:
        return "<div class='wally-advisors-wrap'><p style='padding:12px'>No hay datos para la fecha seleccionada.</p></div>"

    labels = _column_labels()
    period_label = start_date.strftime("%d/%m/%Y") if start_date == end_date else f"{start_date.strftime('%d/%m/%Y')} al {end_date.strftime('%d/%m/%Y')}"
    
    html = ["<div class='wally-advisors-wrap'><table class='wally-advisors'>"]
    html.append(_table_colgroup(rows, columns, labels))
    html.append("<thead>")
    html.append(
        "<tr>"
        "<th rowspan='2'>Sucursal</th>"
        "<th rowspan='2'>Asesor</th>"
        "<th rowspan='2'>Turno</th>"
        "<th rowspan='2'>Cargo</th>"
        "<th rowspan='2'>Estado</th>"
        "<th colspan='2' class='wally-period-accumulated'>Mes Anterior</th>"
        f"<th colspan='8' class='wally-period'>Periodo Actual - {period_label}</th>"
        "</tr>"
    )
    html.append(
        "<tr>"
        "<th>Venta Neta</th>"
        "<th>UPT</th>"
        "<th>Venta Neta</th>"
        "<th>Presupuesto</th>"
        "<th class='wally-th-pendiente'>Pendiente</th>"
        "<th>% Cumpl.</th>"
        "<th>Facturas</th>"
        "<th>Ticket Prom.</th>"
        "<th>UPT</th>"
        "<th>Vr. Unidad Prom.</th>"
        "</tr>"
    )
    html.append("</thead><tbody>")

    previous_branch = None
    alt = False
    for _, row in rows.iterrows():
        branch = str(row["Sucursal"])
        advisor = str(row["Asesor"])
        turno = str(row["Turno"])
        cargo = str(row["Cargo"])
        estado = str(row["Estado"])
        is_subtotal = bool(row["EsSubtotal"])
        row_class = "wally-subtotal" if is_subtotal else ("wally-alt" if alt else "")
        branch_label = branch if previous_branch != branch or is_subtotal else ""
        html.append(f"<tr class='{row_class}'>")
        html.append(f"<td class='wally-branch'>{escape(branch_label)}</td>")
        html.append(f"<td class='wally-advisor'>{escape(advisor)}</td>")
        html.append(f"<td class='wally-turno'>{escape(turno)}</td>")
        html.append(f"<td class='wally-cargo'>{escape(cargo)}</td>")
        html.append(f"<td class='wally-estado'>{escape(estado)}</td>")
        for column in columns:
            if column == "Pendiente":
                html.append(_pending_cell(rows, branch, advisor, is_subtotal))
            else:
                html.append(f"<td>{escape(_cell(rows, branch, advisor, is_subtotal, column))}</td>")
        html.append("</tr>")
        previous_branch = branch
        if not is_subtotal:
            alt = not alt
    html.append("</tbody></table></div>")
    return "".join(html)


def _export_frame(block: pd.DataFrame) -> pd.DataFrame:
    data = _with_subtotals(block)
    if data.empty:
        return data
    data = data.copy()
    columns = [
        "Sucursal",
        "Asesor",
        "Turno",
        "Cargo",
        "VentaPrevQ",
        "UPTPrev",
        "VentaQ",
        "PptoVenta",
        "Pendiente",
        "CumplimientoVenta",
        "Facturas",
        "TicketPromedio",
        "UPT",
        "VrUnidadPromedio",
    ]
    return data[columns]



def _export_pdf_bytes(block: pd.DataFrame, start_date: date, end_date: date) -> bytes:
    import io
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    rows = _with_subtotals(block)
    if rows.empty:
        return b""

    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(letter),
        leftMargin=20,
        rightMargin=20,
        topMargin=20,
        bottomMargin=20
    )

    styles = getSampleStyleSheet()
    
    # Title and Subtitle centered
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=15,
        textColor=colors.HexColor('#0f172a'),
        alignment=1, # Center
        spaceAfter=3
    )
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=10.5,
        textColor=colors.HexColor('#475569'),
        alignment=1, # Center
        spaceAfter=12
    )

    # Table styles for paragraphs to wrap and prevent overflow/debording
    cell_style_left = ParagraphStyle(
        'CellLeft',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=5.5,
        leading=6.5,
        textColor=colors.HexColor('#0f172a')
    )
    cell_style_right = ParagraphStyle(
        'CellRight',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=5.5,
        leading=6.5,
        textColor=colors.HexColor('#0f172a'),
        alignment=2 # Right
    )
    cell_style_center = ParagraphStyle(
        'CellCenter',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=5.5,
        leading=6.5,
        textColor=colors.HexColor('#0f172a'),
        alignment=1 # Center
    )

    subtotal_style_left = ParagraphStyle(
        'SubtotalLeft',
        parent=cell_style_left,
        fontName='Helvetica-Bold'
    )
    subtotal_style_right = ParagraphStyle(
        'SubtotalRight',
        parent=cell_style_right,
        fontName='Helvetica-Bold'
    )
    subtotal_style_center = ParagraphStyle(
        'SubtotalCenter',
        parent=cell_style_center,
        fontName='Helvetica-Bold'
    )

    story = []
    table_data = []

    # Row 0: Header part 1
    row0 = [
        "Sucursal", "Asesor", "Turno", "Cargo", "Estado",
        "Mes Anterior", "",
        f"Periodo Actual - {start_date.strftime('%d/%m/%Y')} al {end_date.strftime('%d/%m/%Y')}", "", "", "", "", "", "", ""
    ]
    # Row 1: Header part 2
    row1 = [
        "", "", "", "", "",
        "Venta Neta", "UPT",
        "Venta Neta", "Presupuesto", "Pendiente", "% Cumpl.", "Facturas", "Ticket Prom.", "UPT", "Vr. Unidad Prom."
    ]
    table_data.append(row0)
    table_data.append(row1)

    t_style = [
        # Merges
        ('SPAN', (0, 0), (0, 1)),
        ('SPAN', (1, 0), (1, 1)),
        ('SPAN', (2, 0), (2, 1)),
        ('SPAN', (3, 0), (3, 1)),
        ('SPAN', (4, 0), (4, 1)),
        ('SPAN', (5, 0), (6, 0)),
        ('SPAN', (7, 0), (14, 0)),
        
        # Grid and borders
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        
        # Header backgrounds and fonts
        ('BACKGROUND', (0, 0), (4, 1), colors.HexColor('#ffffff')),
        ('BACKGROUND', (5, 0), (6, 0), colors.HexColor('#dcfce7')),
        ('BACKGROUND', (7, 0), (14, 0), colors.HexColor('#e9d5ff')),
        ('BACKGROUND', (5, 1), (6, 1), colors.HexColor('#ffffff')),
        ('BACKGROUND', (7, 1), (14, 1), colors.HexColor('#ffffff')),
        
        ('TEXTCOLOR', (0, 0), (4, 1), colors.HexColor('#b91c1c')),
        ('TEXTCOLOR', (5, 0), (6, 1), colors.HexColor('#14532d')),
        ('TEXTCOLOR', (7, 0), (14, 1), colors.HexColor('#581c87')),
        ('FONTNAME', (0, 0), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 1), 6.5),
        ('ALIGN', (0, 0), (-1, 1), 'CENTER'),
    ]

    previous_branch = None
    alt = False
    row_idx = 2
    for _, row in rows.iterrows():
        branch = str(row["Sucursal"])
        advisor = str(row["Asesor"])
        turno = str(row["Turno"])
        cargo = str(row["Cargo"])
        estado = str(row["Estado"])
        is_subtotal = bool(row["EsSubtotal"])
        
        branch_label = branch if previous_branch != branch or is_subtotal else ""
        
        # Determine styles depending on subtotal
        if is_subtotal:
            p_left = subtotal_style_left
            p_right = subtotal_style_right
            p_center = subtotal_style_center
        else:
            p_left = cell_style_left
            p_right = cell_style_right
            p_center = cell_style_center

        # Wrap in Paragraph flowables to wrap or clip text
        # Truncate Asesor to 26 characters if it's very long so it fits neatly in 120pt without wrapping too much.
        if len(advisor) > 28 and not is_subtotal:
            advisor_disp = advisor[:26] + "..."
        else:
            advisor_disp = advisor
            
        r_cols = [
            Paragraph(branch_label, p_left),
            Paragraph(advisor_disp, p_left),
            Paragraph(turno, p_left),
            Paragraph(cargo, p_left),
            Paragraph(estado, p_center)
        ]
        
        for col in REPORT_COLUMNS:
            if col == "Pendiente":
                val_num = float(row.get("Pendiente", 0) or 0)
                val_str = money(abs(val_num))
                # Apply same colors as original report
                if val_num > 0:
                    text_html = f"<font color='#b91c1c'><b>{val_str}</b></font>"
                elif val_num < 0:
                    text_html = f"<font color='#15803d'><b>{val_str}</b></font>"
                else:
                    text_html = val_str
                r_cols.append(Paragraph(text_html, p_right))
            else:
                val = _cell(rows, branch, advisor, is_subtotal, col)
                r_cols.append(Paragraph(val, p_right))
            
        table_data.append(r_cols)
        
        # Background coloring
        if is_subtotal:
            t_style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#e0f2fe')))
        else:
            if alt:
                t_style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#f8fafc')))
            alt = not alt
            
        previous_branch = branch
        row_idx += 1

    col_widths = [50, 135, 42, 55, 40, 45, 30, 45, 50, 45, 35, 40, 45, 30, 50]
    t = Table(table_data, colWidths=col_widths, repeatRows=2)
    t.setStyle(TableStyle(t_style))
    t.hAlign = 'CENTER' # Center horizontally on the page
    
    # Calculate vertical spacing to center vertically
    usable_height = 572 # 612 page height - 40 margins
    title_and_header_height = 15 + 11 + 12 + 24
    data_rows_height = len(rows) * 11
    total_estimated_height = title_and_header_height + data_rows_height
    
    if total_estimated_height < usable_height:
        vertical_spacer_height = (usable_height - total_estimated_height) / 2
        story.append(Spacer(1, vertical_spacer_height))

    story.append(Paragraph("Gerencia Asesores", title_style))
    story.append(Paragraph(f"T-ASE-01 - Detalle por sucursal, asesor, presupuesto y cumplimiento | Periodo: {start_date.strftime('%d/%m/%Y')} al {end_date.strftime('%d/%m/%Y')}", subtitle_style))
    story.append(t)
    
    doc.build(story)
    return output.getvalue()

def render() -> None:
    _report_css()
    page_title("Gerencia Asesores", "T-ASE-01 - Detalle por sucursal, asesor, presupuesto y cumplimiento")
    
    start_date, end_date = _date_filters()
    start, end = db.date_params(start_date, end_date)
    rango_fecha = f"Fecha >= '{start}' AND Fecha < DATEADD(day, 1, '{end}')"

    def format_sucursal(val):
        cleaned = str(val).strip().upper()
        if cleaned in {"PARQUE LAS AMERICAS", "PARQUE LAS AMÉRICAS", "AMERICAS"}:
            return "LAS AMERICAS"
        return cleaned

    try:
        sucursales = optional_multiselect(
            "Sucursal",
            db.distinct_values(db.VIEW_VENTAS, "Sucursal", where=rango_fecha),
            format_func=format_sucursal
        )
        vendedores = optional_multiselect("Asesor", db.distinct_values(db.VIEW_VENTAS, "Vendedor", where=rango_fecha))
    except Exception as exc:
        st.error("No se pudieron cargar filtros de asesores.")
        st.exception(exc)
        return

    try:
        with st.spinner("Cargando reporte Gerencia Asesores..."):
            block_data = _build_block(start_date, end_date, sucursales, vendedores)
    except Exception as exc:
        st.error("No se pudo generar el reporte Gerencia Asesores.")
        st.exception(exc)
        return

    # Metrics cards
    total_curr = block_data.sum(numeric_only=True)
    tot_venta = total_curr.get("VentaQ", 0)
    tot_facturas = total_curr.get("Facturas", 0)
    tot_ppto = total_curr.get("PptoVenta", 0)
    tot_venta_prev = total_curr.get("VentaQ_Prev", 0)
    
    cumplimiento = (tot_venta / tot_ppto) if tot_ppto else 0
    tkt_prom = (tot_venta / tot_facturas) if tot_facturas else 0

    cols = st.columns(6)
    with cols[0]:
        metric_card("Venta Periodo Actual", money(tot_venta))
    with cols[1]:
        metric_card("Facturas Periodo Actual", number(tot_facturas, 0))
    with cols[2]:
        metric_card("Ticket Promedio Actual", money(tkt_prom))
    with cols[3]:
        metric_card("Venta Mes Anterior", money(tot_venta_prev))
    with cols[4]:
        metric_card("Presupuesto Actual", money(tot_ppto))
    with cols[5]:
        metric_card("% Cumplimiento Actual", percent(cumplimiento))

    # Dropdown to filter sucursal in the main page body after the metric cards
    sucursales_disponibles = sorted(list(block_data["Sucursal"].unique()))
    sucursales_options = ["Todas"] + sucursales_disponibles
    
    col_sel, _ = st.columns([0.4, 0.6])
    with col_sel:
        selected_sucursal_main = st.selectbox(
            "Seleccionar Sucursal",
            options=sucursales_options,
            index=0,  # Default to "Todas"
            key="main_body_sucursal_filter"
        )
        
    if selected_sucursal_main != "Todas":
        block_filtered = block_data[block_data["Sucursal"] == selected_sucursal_main].copy()
    else:
        block_filtered = block_data

    section_title("Desempeño Gerencia Asesores")
    tot_ppto_filtered = block_filtered.sum(numeric_only=True).get("PptoVenta", 0)
    if float(tot_ppto_filtered or 0) == 0:
        st.info("No hay presupuesto por asesor cargado para el periodo seleccionado.")
        
    st.markdown(_render_report_table(block_filtered, start_date, end_date, REPORT_COLUMNS), unsafe_allow_html=True)
    st.markdown("<div style='height: 18px'></div>", unsafe_allow_html=True)

    export_df = _export_frame(block_filtered)
    col_exp_1, col_exp_2 = st.columns([0.5, 0.5])
    with col_exp_1:
        st.download_button(
            "Exportar Gerencia Asesores a Excel",
            dataframe_to_excel_bytes({"Gerencia Asesores": export_df}),
            file_name=export_filename("wally_gerencia_asesores"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="btn_export_ger_asesores"
        )
    with col_exp_2:
        pdf_data = _export_pdf_bytes(block_filtered, start_date, end_date)
        st.download_button(
            "Exportar Gerencia Asesores a PDF",
            pdf_data,
            file_name=export_filename("wally_gerencia_asesores", extension="pdf"),
            mime="application/pdf",
            use_container_width=True,
            key="btn_export_ger_asesores_pdf"
        )

    # Place report code in the footer of the page
    st.markdown("<div style='height: 15px'></div>", unsafe_allow_html=True)
    code_footer(*get_code("asesores", "detail_table"))
