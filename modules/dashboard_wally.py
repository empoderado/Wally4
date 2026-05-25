from __future__ import annotations

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
from services.ui import code_footer, display_table, metric_card, page_title, section_title, warning_box


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
            SUM(ISNULL(VentaNetaQ, 0)) - SUM(ISNULL(CostoTotal, 0)) AS MargenQ
        FROM {db.VIEW_VENTAS}
        WHERE CAST(Fecha AS date) BETWEEN ? AND ?
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
            ,SUM(ISNULL(VentaNetaQ, 0)) - SUM(ISNULL(CostoTotal, 0)) AS MargenQ
        FROM {db.VIEW_VENTAS}
        WHERE CAST(Fecha AS date) BETWEEN ? AND ?
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
        WHERE CAST(Fecha AS date) BETWEEN ? AND ?
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


def render() -> None:
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
        metric_card("Margen", money(margen), percent(margen / venta if venta else 0), positive=margen >= 0)
    code_footer(*get_code("dashboard", "report"))

    section_title("Resumen por Sucursal")
    kpis = kpis_sucursal(by_branch)
    display_table(kpis, height=430)
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
