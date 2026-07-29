from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from services import db
from services.charts import WALLY_COLORS, horizontal_bar_layout
from services.catalog import get_code
from services.exports import dataframe_to_excel_bytes, export_filename
from services.filters import date_sidebar, optional_multiselect
from services.formatting import money, number, percent
from services.report_controls import chart_type_control, color_picker, dimension_control, metric_control, render_custom_chart, top_n_control
from services.ui import code_footer, display_table, metric_card, page_title, section_title


def _where(filters: dict[str, list[str]]) -> str:
    clauses = []
    for column, values in filters.items():
        if values:
            clauses.append(f"{column} IN ({db.sql_literal_list(values)})")
    return " AND ".join(clauses) if clauses else "1=1"


def render() -> None:
    page_title("Ventas", "Analisis por sucursal, vendedor, linea, tipo de prenda y referencia")
    code_footer(*get_code("ventas", "report"))
    start_date, end_date = date_sidebar()
    start, end = db.date_params(start_date, end_date)
    rango_fecha = f"Fecha >= '{start}' AND Fecha < DATEADD(day, 1, '{end}')"
    try:
        sucursales = optional_multiselect("Sucursal", db.distinct_values(db.VIEW_VENTAS, "Sucursal", where=rango_fecha))
        lineas = optional_multiselect("Linea", db.distinct_values(db.VIEW_VENTAS, "Linea", where=rango_fecha))
        tipos = optional_multiselect("Tipo prenda", db.distinct_values(db.VIEW_VENTAS, "DescripTipoPrenda", where=rango_fecha))
        vendedores = optional_multiselect("Vendedor", db.distinct_values(db.VIEW_VENTAS, "Vendedor", where=rango_fecha))
    except Exception as exc:
        st.error("No se pudieron cargar filtros de ventas.")
        st.exception(exc)
        return
    st.sidebar.markdown("### Personalización")
    dimension = dimension_control(["Sucursal", "Vendedor", "Linea", "DescripTipoPrenda", "Referencia"], "Sucursal")
    metric = metric_control(["VentaNetaQ", "Unidades", "Facturas", "DescuentoQ", "MargenQ"], "VentaNetaQ")
    chart_type = chart_type_control("Barras verticales", ["Barras horizontales", "Barras verticales", "Dona"])
    custom_color = color_picker()
    top_n = top_n_control(default=15, max_value=50)

    where_extra = _where({"Sucursal": sucursales, "Linea": lineas, "DescripTipoPrenda": tipos, "Vendedor": vendedores})

    try:
        data = db.read_sql(
            f"""
            SELECT
                Sucursal,
                Vendedor,
                Linea,
                DescripTipoPrenda,
                Referencia,
                SUM(ISNULL(VentaNetaQ, 0)) AS VentaNetaQ,
                SUM(ISNULL(Unidades, 0)) AS Unidades,
                COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END) AS Facturas,
                SUM(ISNULL(DescuentoValor, 0)) AS DescuentoQ,
                SUM(ISNULL(VentaNetaQ, 0)) - SUM(ISNULL(CostoTotal, 0)) AS MargenQ
            FROM {db.VIEW_VENTAS}
            WHERE Fecha >= ? AND Fecha < DATEADD(day, 1, ?)
              AND {where_extra}
            GROUP BY Sucursal, Vendedor, Linea, DescripTipoPrenda, Referencia
            ORDER BY VentaNetaQ DESC
            """,
            (start, end),
        )
    except Exception as exc:
        st.error("No se pudieron cargar ventas.")
        st.exception(exc)
        return

    if data.empty:
        st.info("No hay ventas con los filtros seleccionados.")
        return

    venta_total = float(data["VentaNetaQ"].sum())
    unidades_total = float(data["Unidades"].sum())
    facturas_total = float(data["Facturas"].sum())
    margen_total = float(data["MargenQ"].sum())
    ticket_promedio = venta_total / facturas_total if facturas_total else 0
    upt = unidades_total / facturas_total if facturas_total else 0
    vr_unidad_promedio = venta_total / unidades_total if unidades_total else 0

    cols = st.columns(7)
    with cols[0]:
        metric_card("Venta Neta Q", money(venta_total))
    with cols[1]:
        metric_card("Unidades", number(unidades_total))
    with cols[2]:
        metric_card("Facturas", number(facturas_total))
    with cols[3]:
        metric_card("Ticket Promedio", money(ticket_promedio))
    with cols[4]:
        metric_card("UPT", number(upt, 2))
    with cols[5]:
        metric_card("Vr Unidad Prom.", money(vr_unidad_promedio))
    with cols[6]:
        metric_card("Margen", money(margen_total), percent(margen_total / venta_total if venta_total else 0), positive=margen_total >= 0)

    section_title(f"{metric} por {dimension}")
    render_custom_chart(data, dimension, metric, chart_type, custom_color, top_n, height=430)
    code_footer(*get_code("ventas", "main_chart"))

    section_title("Detalle de Ventas")
    display_table(data, height=460)
    code_footer(*get_code("ventas", "detail_table"))
    st.download_button(
        "Exportar ventas a Excel",
        dataframe_to_excel_bytes({"Ventas": data}),
        file_name=export_filename("wally_ventas"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
