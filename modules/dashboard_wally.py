from __future__ import annotations

from html import escape

import pandas as pd
import plotly.express as px
import streamlit as st

from services import db
from services.calculations import kpis_sucursal
from services.charts import WALLY_COLORS, apply_chart_theme
from services.catalog import get_code
from services.exports import dataframe_to_excel_bytes, export_filename
from services.filters import date_sidebar
from services.formatting import money, number, percent
from services.report_controls import chart_type_control, color_picker, metric_control, render_custom_chart, top_n_control
from services.ui import code_footer, metric_card, page_title, section_title, warning_box


BRANCH_TABLE_COLUMNS = [
    "Ranking",
    "Sucursal",
    "Unidades",
    "VentaNetaQ",
    "Facturas",
    "Upt",
    "FactProm",
    "VrPromedioUnidad",
    "MargenQ",
    "%Margen",
    "DescuentoQ",
    "%Desc",
    "%VentaSuc",
    "Semáforo",
]

BRANCH_TABLE_LABELS = {
    "Ranking": "Ranking",
    "Sucursal": "Sucursal",
    "Unidades": "Unidades",
    "VentaNetaQ": "Venta Neta Q",
    "Facturas": "Facturas",
    "Upt": "UPT",
    "FactProm": "Ticket Promedio",
    "VrPromedioUnidad": "Vr Unidad Promedio",
    "MargenQ": "Margen Q",
    "%Margen": "% Margen",
    "DescuentoQ": "Descuento Q",
    "%Desc": "% Descuento",
    "%VentaSuc": "% Venta Sucursal",
    "Semáforo": "Semaforo",
}


def _load_dashboard(start_date, end_date) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    start, end = db.date_params(start_date, end_date)
    summary = db.read_sql(
        f"""
        SELECT
            SUM(ISNULL(VentaNetaQ, 0)) AS VentaNetaQ,
            SUM(ISNULL(Unidades, 0)) AS Unidades,
            COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END) AS Facturas,
            SUM(ISNULL(VentaBruta, 0)) AS VentaBruta,
            SUM(ISNULL(DescuentoValor, 0)) AS DescuentoQ,
            SUM(ISNULL(CostoTotal, 0)) AS CostoTotal,
            SUM(ISNULL(VentaNetaQ, 0)) / 1.12 - SUM(ISNULL(CostoTotal, 0)) AS MargenQ
        FROM {db.VIEW_VENTAS}
        WHERE Fecha >= ? AND Fecha < DATEADD(day, 1, ?)
        """,
        (start, end),
    )
    by_branch = db.read_sql(
        f"""
        SELECT
            Sucursal,
            SUM(ISNULL(VentaNetaQ, 0)) AS VentaNetaQ,
            SUM(ISNULL(Unidades, 0)) AS Unidades,
            COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END) AS Facturas
            ,SUM(ISNULL(VentaBruta, 0)) AS VentaBruta
            ,SUM(ISNULL(DescuentoValor, 0)) AS DescuentoQ
            ,SUM(ISNULL(CostoTotal, 0)) AS CostoTotal
            ,SUM(ISNULL(VentaNetaQ, 0)) / 1.12 - SUM(ISNULL(CostoTotal, 0)) AS MargenQ
        FROM {db.VIEW_VENTAS}
        WHERE Fecha >= ? AND Fecha < DATEADD(day, 1, ?)
        GROUP BY Sucursal
        ORDER BY VentaNetaQ DESC
        """,
        (start, end),
    )
    by_hour = db.read_sql(
        f"""
        SELECT
            CASE
                WHEN DATEPART(hour, CAST(HoraDocumento AS time)) = 0 THEN 24
                ELSE DATEPART(hour, CAST(HoraDocumento AS time))
            END AS Hora,
            SUM(ISNULL(VentaNetaQ, 0)) AS VentaNetaQ,
            SUM(ISNULL(Unidades, 0)) AS Unidades
        FROM {db.VIEW_VENTAS}
        WHERE Fecha >= ? AND Fecha < DATEADD(day, 1, ?)
          AND (
                DATEPART(hour, CAST(HoraDocumento AS time)) BETWEEN 8 AND 23
                OR DATEPART(hour, CAST(HoraDocumento AS time)) = 0
          )
        GROUP BY
            CASE
                WHEN DATEPART(hour, CAST(HoraDocumento AS time)) = 0 THEN 24
                ELSE DATEPART(hour, CAST(HoraDocumento AS time))
            END
        ORDER BY Hora
        """,
        (start, end),
    )
    if by_hour.empty or "Hora" not in by_hour.columns:
        by_hour = pd.DataFrame({"Hora": list(range(8, 25)), "VentaNetaQ": 0, "Unidades": 0})
    else:
        by_hour = (
            by_hour.set_index("Hora")
            .reindex(range(8, 25), fill_value=0)
            .rename_axis("Hora")
            .reset_index()
        )
    by_hour["HoraLabel"] = by_hour["Hora"].map(lambda hour: "24:00" if int(hour) == 24 else f"{int(hour):02d}:00")
    return summary, by_branch, by_hour


def _branch_table_css() -> None:
    st.markdown(
        """
        <style>
        .wally-branch-summary-wrap {
            width: 100%;
            overflow-x: auto;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            background: #ffffff;
            box-shadow: 0 2px 10px rgba(15, 23, 42, .04);
        }
        table.wally-branch-summary {
            border-collapse: collapse;
            width: max-content;
            min-width: 100%;
            font-size: 12px;
        }
        table.wally-branch-summary th,
        table.wally-branch-summary td {
            border: 1px solid #cbd5e1;
            padding: 6px 8px;
            white-space: nowrap;
        }
        table.wally-branch-summary th {
            background: #ffffff;
            color: #b91c1c;
            font-weight: 850;
            text-transform: uppercase;
            text-align: center;
            white-space: normal;
            line-height: 1.12;
            vertical-align: middle;
        }
        table.wally-branch-summary th.wally-group {
            background: #eef2ff;
            color: #111827;
            font-size: 13px;
        }
        table.wally-branch-summary th.wally-margin-group,
        table.wally-branch-summary th.wally-margin-column {
            background: #fff7ed;
            color: #9a3412;
        }
        table.wally-branch-summary td {
            text-align: right;
            color: #0f172a;
        }
        table.wally-branch-summary td.wally-branch-name {
            text-align: left;
            font-weight: 700;
        }
        table.wally-branch-summary td.wally-margin-column {
            background: #fffaf0;
        }
        table.wally-branch-summary td.wally-margin-low {
            color: #b91c1c;
            font-weight: 850;
        }
        table.wally-branch-summary tr.wally-alt td {
            background: #f8fafc;
        }
        table.wally-branch-summary tr.wally-alt td.wally-margin-column {
            background: #fff7ed;
        }
        table.wally-branch-summary tr.wally-total td {
            background: #e0f2fe;
            color: #0f172a;
            font-weight: 850;
            border-top: 2px solid #334155;
        }
        table.wally-branch-summary tr.wally-total td.wally-margin-column {
            background: #ffedd5;
        }
        table.wally-branch-summary tr.wally-total td.wally-margin-low {
            color: #b91c1c;
        }
        .wally-status {
            display: inline-block;
            min-width: 62px;
            padding: 2px 7px;
            border-radius: 999px;
            text-align: center;
            font-size: 10px;
            font-weight: 850;
            text-transform: uppercase;
        }
        .wally-status-green {
            background: #dcfce7;
            color: #166534;
        }
        .wally-status-yellow {
            background: #fef3c7;
            color: #92400e;
        }
        .wally-status-red {
            background: #fee2e2;
            color: #991b1b;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _branch_total_row(data: pd.DataFrame) -> dict[str, object]:
    unidades = float(data["Unidades"].sum())
    venta = float(data["VentaNetaQ"].sum())
    facturas = float(data["Facturas"].sum())
    margen = float(data["MargenQ"].sum())
    descuento = float(data["DescuentoQ"].sum())
    venta_bruta = sum(
        float(row["DescuentoQ"]) / float(row["%Desc"])
        for _, row in data.iterrows()
        if float(row.get("%Desc", 0) or 0) > 0
    )
    margen_pct = margen / (venta / 1.12) if venta else 0
    if margen_pct >= 0.60:
        semaforo = "Verde"
    elif margen_pct >= 0.55:
        semaforo = "Amarillo"
    else:
        semaforo = "Rojo"
    return {
        "Ranking": "",
        "Sucursal": "Total",
        "Unidades": unidades,
        "VentaNetaQ": venta,
        "Facturas": facturas,
        "Upt": unidades / facturas if facturas else 0,
        "FactProm": venta / facturas if facturas else 0,
        "VrPromedioUnidad": venta / unidades if unidades else 0,
        "MargenQ": margen,
        "%Margen": margen_pct,
        "DescuentoQ": descuento,
        "%Desc": descuento / venta_bruta if venta_bruta else 0,
        "%VentaSuc": 1 if venta else 0,
        "Semáforo": semaforo,
    }


def _branch_cell(column: str, value: object) -> str:
    if pd.isna(value) or value == "":
        return ""
    if column in {"VentaNetaQ", "FactProm", "VrPromedioUnidad", "MargenQ", "DescuentoQ"}:
        return money(value)
    if column in {"%Margen", "%Desc", "%VentaSuc"}:
        return percent(value)
    if column == "Upt":
        return number(value, 2)
    if column in {"Ranking", "Unidades", "Facturas"}:
        return number(value, 0)
    return str(value)


def _status_html(value: object) -> str:
    status = str(value or "").strip()
    status_class = {
        "Verde": "green",
        "Amarillo": "yellow",
        "Rojo": "red",
    }.get(status, "red")
    return f"<span class='wally-status wally-status-{status_class}'>{escape(status)}</span>"


def _render_branch_table(data: pd.DataFrame) -> str:
    if data.empty:
        return "<div class='wally-branch-summary-wrap'><p style='padding:12px'>No hay datos por sucursal para el periodo seleccionado.</p></div>"

    rows = data.copy()
    rows = pd.concat([rows, pd.DataFrame([_branch_total_row(rows)])], ignore_index=True)
    html = ["<div class='wally-branch-summary-wrap'><table class='wally-branch-summary'>"]
    html.append(
        "<thead><tr>"
        "<th class='wally-group' colspan='2'>Sucursal</th>"
        "<th class='wally-group' colspan='3'>Ventas</th>"
        "<th class='wally-group' colspan='3'>KPIS</th>"
        "<th class='wally-group wally-margin-group' colspan='2'>Margen</th>"
        "<th class='wally-group' colspan='2'>Descuento</th>"
        "<th class='wally-group' colspan='2'>Participacion</th>"
        "</tr><tr>"
    )
    for column in BRANCH_TABLE_COLUMNS:
        css_class = " class='wally-margin-column'" if column == "%Margen" else ""
        html.append(f"<th{css_class}>{escape(BRANCH_TABLE_LABELS[column])}</th>")
    html.append("</tr></thead><tbody>")

    last_index = len(rows) - 1
    for index, row in rows.iterrows():
        row_class = "wally-total" if index == last_index else ("wally-alt" if index % 2 else "")
        html.append(f"<tr class='{row_class}'>")
        for column in BRANCH_TABLE_COLUMNS:
            value = row.get(column, "")
            classes = []
            if column == "Sucursal":
                classes.append("wally-branch-name")
            if column == "%Margen":
                classes.append("wally-margin-column")
                try:
                    if float(value) < 0.54:
                        classes.append("wally-margin-low")
                except (TypeError, ValueError):
                    pass
            class_attr = f" class='{' '.join(classes)}'" if classes else ""
            content = _status_html(value) if column == "Semáforo" else escape(_branch_cell(column, value))
            html.append(f"<td{class_attr}>{content}</td>")
        html.append("</tr>")
    html.append("</tbody></table></div>")
    return "".join(html)


def render() -> None:
    _branch_table_css()
    page_title("Resumen Ventas", "Indicadores principales de ventas")
    start_date, end_date = date_sidebar()
    st.sidebar.markdown("### Personalización")
    dashboard_metric = metric_control(["VentaNetaQ", "Unidades", "Facturas"], "VentaNetaQ")
    dashboard_chart = chart_type_control("Barras verticales", ["Barras horizontales", "Barras verticales", "Dona"])
    dashboard_color = color_picker()
    dashboard_top_n = top_n_control(default=12, max_value=30)
    try:
        summary, by_branch, by_hour = _load_dashboard(start_date, end_date)
    except Exception as exc:
        st.error("No se pudo cargar el dashboard.")
        st.exception(exc)
        return

    if summary.empty:
        warning_box("No hay datos para el periodo seleccionado.")
        return

    row = summary.iloc[0].fillna(0)
    venta = float(row["VentaNetaQ"] or 0)
    unidades = float(row["Unidades"] or 0)
    facturas = float(row["Facturas"] or 0)
    margen = float(row["MargenQ"] or 0)
    venta_bruta = float(row["VentaBruta"] or 0)
    descuento = float(row["DescuentoQ"] or 0)
    ticket = venta / facturas if facturas else 0
    upt = unidades / facturas if facturas else 0
    vr_unidad = venta / unidades if unidades else 0

    cols = st.columns(7)
    with cols[0]:
        metric_card("Venta Neta Q", money(venta))
    with cols[1]:
        metric_card("Unidades", number(unidades))
    with cols[2]:
        metric_card("Facturas", number(facturas))
    with cols[3]:
        metric_card("Ticket Promedio", money(ticket))
    with cols[4]:
        metric_card("UPT", number(upt, 2))
    with cols[5]:
        metric_card("Vr Unidad Prom.", money(vr_unidad))
    with cols[6]:
        metric_card("Margen", money(margen), percent(margen / (venta / 1.12) if venta else 0), positive=margen >= 0)
    code_footer(*get_code("dashboard", "report"))

    section_title("Resumen por Sucursal")
    kpis = kpis_sucursal(by_branch)
    st.markdown(_render_branch_table(kpis), unsafe_allow_html=True)
    code_footer(*get_code("dashboard", "branch_table"))

    cols = st.columns(2)
    with cols[0]:
        section_title(f"{dashboard_metric} por Sucursal")
        if not by_branch.empty:
            render_custom_chart(by_branch, "Sucursal", dashboard_metric, dashboard_chart, dashboard_color, dashboard_top_n, height=380)
            code_footer(*get_code("dashboard", "branch_chart"))
    with cols[1]:
        section_title("Venta Neta Q por Hora")
        if not by_hour.empty:
            fig = px.line(by_hour, x="HoraLabel", y="VentaNetaQ", markers=True, color_discrete_sequence=[WALLY_COLORS[0]])
            fig.update_traces(line=dict(width=3), marker=dict(size=7))
            fig.update_xaxes(title_text="Hora", categoryorder="array", categoryarray=by_hour["HoraLabel"].tolist())
            fig.update_yaxes(title_text="Venta Neta Q")
            fig = apply_chart_theme(fig, 380)
            st.plotly_chart(fig, use_container_width=True)
            code_footer(*get_code("dashboard", "time_chart"))
    st.download_button(
        "Exportar resumen a Excel",
        dataframe_to_excel_bytes({"Resumen": summary, "KPIS Sucursal": kpis, "Venta por Hora": by_hour}),
        file_name=export_filename("wally_dashboard"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
