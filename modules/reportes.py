from __future__ import annotations

import streamlit as st
import plotly.express as px

from services import db
from services.calculations import kpis_sucursal
from services.charts import WALLY_COLORS, apply_chart_theme, horizontal_bar_layout
from services.catalog import get_code
from services.exports import dataframe_to_excel_bytes, export_filename
from services.filters import date_sidebar
from services.formatting import money, number, percent
from services.report_controls import (
    chart_type_control,
    color_picker,
    dimension_control,
    metric_control,
    render_custom_chart,
    top_n_control,
)
from services.ui import code_footer, display_table, metric_card, page_title, section_title


def _ensure_columns(data, defaults):
    for column, default in defaults.items():
        if column not in data.columns:
            data[column] = default
    return data


def render() -> None:
    page_title("Reportes", "Exportaciones gerenciales desde las vistas oficiales de Wally")
    code_footer(*get_code("reportes", "report"))
    start_date, end_date = date_sidebar()
    reporte = st.selectbox(
        "Reporte",
        [
            "KPIS Sucursal",
            "Clientes CRM",
            "Existencias",
            "Entradas Inventario",
        ],
    )
    st.sidebar.markdown("### Personalización")
    custom_color = color_picker()
    top_n = top_n_control(default=15, max_value=100)

    try:
        if reporte == "KPIS Sucursal":
            start, end = db.date_params(start_date, end_date)
            data = db.read_sql(
                f"""
                SELECT
                    Sucursal,
                    SUM(ISNULL(Unidades, 0)) AS Unidades,
                    SUM(ISNULL(VentaNetaQ, 0)) AS VentaNetaQ,
                    COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END) AS Facturas,
                    SUM(ISNULL(VentaNetaQ, 0)) - SUM(ISNULL(CostoTotal, 0)) AS MargenQ,
                    SUM(ISNULL(DescuentoValor, 0)) AS DescuentoQ,
                    SUM(ISNULL(VentaBruta, 0)) AS VentaBruta
                FROM {db.VIEW_VENTAS}
                WHERE CAST(Fecha AS date) BETWEEN ? AND ?
                GROUP BY Sucursal
                ORDER BY VentaNetaQ DESC
                """,
                (start, end),
            )
        elif reporte == "Clientes CRM":
            data = db.read_sql(f"SELECT TOP 5000 * FROM {db.VIEW_CRM} ORDER BY DiasSinCompra DESC, VentaNetaTotal DESC")
        elif reporte == "Existencias":
            data = db.read_sql(f"SELECT TOP 5000 * FROM {db.VIEW_EXISTENCIA} ORDER BY CodEmbarqueAbreviado DESC, ExistenciaDisponible DESC")
        else:
            data = db.read_sql(f"SELECT TOP 5000 * FROM {db.VIEW_ENTRADAS} ORDER BY FechaEntrada DESC, UnidadesEntrada DESC")
    except Exception as exc:
        st.error("No se pudo generar el reporte.")
        st.exception(exc)
        return

    if data.empty:
        st.info("No hay datos para este reporte.")
        return

    if reporte == "KPIS Sucursal":
        data = _ensure_columns(
            data,
            {
                "Sucursal": "",
                "Unidades": 0,
                "VentaNetaQ": 0,
                "Facturas": 0,
                "MargenQ": 0,
                "DescuentoQ": 0,
                "VentaBruta": 0,
            },
        )
        data = kpis_sucursal(data)
        dimension = dimension_control(["Sucursal"], "Sucursal")
        metric = metric_control(["VentaNetaQ", "Unidades", "Facturas", "MargenQ", "DescuentoQ", "VrPromedioUnidad"], "VentaNetaQ")
        chart_type = chart_type_control("Barras verticales", ["Barras horizontales", "Barras verticales", "Dona"])
        total_venta = float(data["VentaNetaQ"].sum())
        total_unidades = float(data["Unidades"].sum())
        total_facturas = float(data["Facturas"].sum())
        total_margen = float(data["MargenQ"].sum())
        total_descuento = float(data["DescuentoQ"].sum())
        total_vr_unidad = total_venta / total_unidades if total_unidades else 0
        cols = st.columns(6)
        with cols[0]:
            metric_card("Venta Neta Q", money(total_venta))
        with cols[1]:
            metric_card("Unidades", number(total_unidades))
        with cols[2]:
            metric_card("Facturas", number(total_facturas))
        with cols[3]:
            metric_card("Margen Q", money(total_margen), percent(total_margen / total_venta if total_venta else 0), positive=total_margen >= 0)
        with cols[4]:
            metric_card("Descuento Q", money(total_descuento), percent(total_descuento / total_venta if total_venta else 0))
        with cols[5]:
            metric_card("Vr Unidad Prom.", money(total_vr_unidad))

        cols = st.columns(2)
        with cols[0]:
            section_title(f"{metric} por {dimension}")
            render_custom_chart(data, dimension, metric, chart_type, custom_color, top_n)
            code_footer(*get_code("reportes", "custom_chart"))
        with cols[1]:
            section_title("Margen vs Descuento")
            fig = px.scatter(
                data,
                x="DescuentoQ",
                y="MargenQ",
                size="VentaNetaQ",
                color="Sucursal",
                color_discrete_sequence=WALLY_COLORS,
                hover_data=["VentaNetaQ", "Unidades", "Facturas"],
            )
            st.plotly_chart(apply_chart_theme(fig, 390), use_container_width=True)

    elif reporte == "Clientes CRM":
        data = _ensure_columns(
            data,
            {
                "SegmentoSinCompra": "",
                "SucursalPreferida": "",
                "VendedorUltimaFactura": "",
                "VentaNetaTotal": 0,
                "FacturasTotales": 0,
                "UnidadesTotales": 0,
                "DiasSinCompra": 0,
                "Celular": "",
            },
        )
        dimension = dimension_control(["SegmentoSinCompra", "SucursalPreferida", "VendedorUltimaFactura"], "SegmentoSinCompra")
        metric = metric_control(["VentaNetaTotal", "FacturasTotales", "UnidadesTotales", "DiasSinCompra"], "VentaNetaTotal")
        chart_type = chart_type_control("Barras verticales", ["Barras horizontales", "Barras verticales", "Dona"])
        cols = st.columns(4)
        with cols[0]:
            metric_card("Clientes", number(len(data)))
        with cols[1]:
            metric_card("Venta Historica", money(data["VentaNetaTotal"].sum()))
        with cols[2]:
            metric_card("Dias sin compra prom.", number(data["DiasSinCompra"].mean(), 1))
        with cols[3]:
            metric_card("Con celular", number(data["Celular"].fillna("").astype(str).str.strip().ne("").sum()))
        section_title(f"{metric} por {dimension}")
        render_custom_chart(data, dimension, metric, chart_type, custom_color, top_n, height=350)
        code_footer(*get_code("reportes", "custom_chart"))

    elif reporte == "Existencias":
        data = _ensure_columns(
            data,
            {
                "Sucursal": "",
                "Linea": "",
                "DescripTipoPrenda": "",
                "CodEmbarqueAbreviado": "",
                "ExistenciaDisponible": 0,
                "ExistenciaFisica": 0,
                "TVida": 0,
                "Referencia": "",
            },
        )
        dimension = dimension_control(["Sucursal", "Linea", "DescripTipoPrenda", "CodEmbarqueAbreviado"], "Linea")
        metric = metric_control(["ExistenciaDisponible", "ExistenciaFisica", "TVida"], "ExistenciaDisponible")
        chart_type = chart_type_control("Barras verticales", ["Barras horizontales", "Barras verticales", "Dona"])
        cols = st.columns(3)
        with cols[0]:
            metric_card("Existencia Disponible", number(data["ExistenciaDisponible"].sum()))
        with cols[1]:
            metric_card("Existencia Fisica", number(data["ExistenciaFisica"].sum()))
        with cols[2]:
            metric_card("Referencias", number(data["Referencia"].nunique()))
        section_title(f"{metric} por {dimension}")
        render_custom_chart(data, dimension, metric, chart_type, custom_color, top_n, height=380)
        code_footer(*get_code("reportes", "custom_chart"))

    elif reporte == "Entradas Inventario":
        data = _ensure_columns(
            data,
            {
                "FechaEntrada": "",
                "Sucursal": "",
                "Linea": "",
                "DescripTipoPrenda": "",
                "CodEmbarqueAbreviado": "",
                "UnidadesEntrada": 0,
                "Referencia": "",
            },
        )
        dimension = dimension_control(["FechaEntrada", "Sucursal", "Linea", "DescripTipoPrenda", "CodEmbarqueAbreviado"], "FechaEntrada")
        metric = metric_control(["UnidadesEntrada"], "UnidadesEntrada")
        chart_type = chart_type_control("Línea", ["Línea", "Barras horizontales", "Barras verticales", "Dona"])
        cols = st.columns(3)
        with cols[0]:
            metric_card("Unidades Entrada", number(data["UnidadesEntrada"].sum()))
        with cols[1]:
            metric_card("Referencias", number(data["Referencia"].nunique()))
        with cols[2]:
            metric_card("Sucursales", number(data["Sucursal"].nunique()))
        section_title(f"{metric} por {dimension}")
        render_custom_chart(data, dimension, metric, chart_type, custom_color, top_n, height=360)
        code_footer(*get_code("reportes", "custom_chart"))

    section_title(f"Detalle - {reporte}")
    display_table(data, height=470)
    code_footer(*get_code("reportes", "detail_table"))
    st.download_button(
        "Exportar reporte a Excel",
        dataframe_to_excel_bytes({reporte: data}),
        file_name=export_filename("wally_reporte"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
