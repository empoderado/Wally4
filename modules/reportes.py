from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from modules.dashboard_wally import _branch_table_css, _render_branch_table
from modules.gerencia import (
    _load_branch_range_comparison,
    _load_daily_comparison,
    _load_line_performance,
    _load_recent_shipment_summary,
)
from services import db
from services.calculations import kpis_sucursal
from services.catalog import get_code
from services.executive_report_exports import (
    executive_report_to_excel_bytes,
    executive_report_to_pdf_bytes,
)
from services.executive_tables import (
    render_branch_range_comparison_table,
    render_daily_comparison_table,
    render_line_performance_table,
    render_shipment_summary_table,
)
from services.exports import export_filename
from services.formatting import money, number, percent
from services.ui import code_footer, metric_card, section_title


def _report_heading() -> None:
    st.markdown(
        """
        <div class="wally-page-heading">
            <div class="wally-eyebrow">Wally4</div>
            <h1>Reportes</h1>
            <div class="wally-subtitle">Generacion y exportacion de informes ejecutivos</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _default_dates() -> tuple[date, date]:
    today = date.today()
    return today.replace(day=1), today


def _load_sales_summary(start_date: date, end_date: date) -> tuple[pd.DataFrame, pd.DataFrame]:
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
        WHERE Fecha >= ? AND Fecha < DATEADD(day, 1, ?)
        """,
        (start, end),
    )
    branches = db.read_sql(
        f"""
        SELECT
            Sucursal,
            SUM(ISNULL(VentaNetaQ, 0)) AS VentaNetaQ,
            SUM(ISNULL(Unidades, 0)) AS Unidades,
            COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END) AS Facturas,
            SUM(ISNULL(VentaBruta, 0)) AS VentaBruta,
            SUM(ISNULL(DescuentoValor, 0)) AS DescuentoQ,
            SUM(ISNULL(CostoTotal, 0)) AS CostoTotal,
            SUM(ISNULL(VentaNetaQ, 0)) - SUM(ISNULL(CostoTotal, 0)) AS MargenQ
        FROM {db.VIEW_VENTAS}
        WHERE Fecha >= ? AND Fecha < DATEADD(day, 1, ?)
        GROUP BY Sucursal
        ORDER BY VentaNetaQ DESC
        """,
        (start, end),
    )
    return summary, branches


def _kpi_frame(summary: pd.DataFrame) -> pd.DataFrame:
    row = summary.iloc[0].fillna(0) if not summary.empty else pd.Series(dtype=float)
    venta = float(row.get("VentaNetaQ", 0) or 0)
    unidades = float(row.get("Unidades", 0) or 0)
    facturas = float(row.get("Facturas", 0) or 0)
    margen = float(row.get("MargenQ", 0) or 0)
    descuento = float(row.get("DescuentoQ", 0) or 0)
    return pd.DataFrame(
        [
            {"Indicador": "Venta Neta Q", "Valor": venta},
            {"Indicador": "Unidades", "Valor": unidades},
            {"Indicador": "Facturas", "Valor": facturas},
            {"Indicador": "Ticket Promedio", "Valor": venta / facturas if facturas else 0},
            {"Indicador": "UPT", "Valor": unidades / facturas if facturas else 0},
            {"Indicador": "Vr Unidad Promedio", "Valor": venta / unidades if unidades else 0},
            {"Indicador": "Margen Q", "Valor": margen},
            {"Indicador": "% Margen", "Valor": margen / venta if venta else 0},
            {"Indicador": "Descuento Q", "Valor": descuento},
        ]
    )


def _render_kpis(summary: pd.DataFrame) -> None:
    row = summary.iloc[0].fillna(0)
    venta = float(row.get("VentaNetaQ", 0) or 0)
    unidades = float(row.get("Unidades", 0) or 0)
    facturas = float(row.get("Facturas", 0) or 0)
    margen = float(row.get("MargenQ", 0) or 0)
    cols = st.columns(7)
    values = [
        ("Venta Neta Q", money(venta), "", None),
        ("Unidades", number(unidades), "", None),
        ("Facturas", number(facturas), "", None),
        ("Ticket Promedio", money(venta / facturas if facturas else 0), "", None),
        ("UPT", number(unidades / facturas if facturas else 0, 2), "", None),
        ("Vr Unidad Prom.", money(venta / unidades if unidades else 0), "", None),
        ("Margen", money(margen), percent(margen / venta if venta else 0), margen >= 0),
    ]
    for column, (label, value, delta, positive) in zip(cols, values):
        with column:
            metric_card(label, value, delta, positive=positive)


def _load_executive_report(start_date: date, end_date: date) -> dict[str, object]:
    summary, branches = _load_sales_summary(start_date, end_date)
    daily, daily_years = _load_daily_comparison(start_date, end_date)
    branch_comparison, branch_years = _load_branch_range_comparison(start_date, end_date)
    return {
        "summary": summary,
        "branch_kpis": kpis_sucursal(branches),
        "line_performance": _load_line_performance(start_date, end_date),
        "branch_comparison": branch_comparison,
        "branch_years": branch_years,
        "daily": daily,
        "daily_years": daily_years,
        "shipments": _load_recent_shipment_summary(),
    }


def _export_sections(report: dict[str, object]) -> dict[str, pd.DataFrame]:
    return {
        "R-DASH-01": _kpi_frame(report["summary"]),
        "T-DASH-01": report["branch_kpis"],
        "T-GER-05": report["line_performance"],
        "T-GER-04": report["branch_comparison"],
        "T-GER-03": report["daily"],
        "T-EXI-02": report["shipments"],
    }


def render() -> None:
    _branch_table_css()
    _report_heading()
    default_start, default_end = _default_dates()
    st.sidebar.markdown("### Generacion de reportes")
    report_name = st.sidebar.selectbox(
        "Reporte",
        ["Resumen Ejecutivo"],
        key="reportes_tipo",
    )
    start_date = st.sidebar.date_input(
        "Fecha inicio",
        value=default_start,
        key="reportes_fecha_inicio",
    )
    end_date = st.sidebar.date_input(
        "Fecha final",
        value=default_end,
        key="reportes_fecha_final",
    )
    generate = st.sidebar.button(
        "Generar reporte",
        type="primary",
        use_container_width=True,
        key="reportes_generar",
    )
    st.sidebar.caption("PDF carta horizontal, margenes de 1 cm, encabezado y pie de pagina.")

    if generate:
        if start_date > end_date:
            st.sidebar.error("La fecha inicio no puede ser mayor que la fecha final.")
        else:
            st.session_state["reportes_solicitud"] = {
                "name": report_name,
                "start": start_date,
                "end": end_date,
            }

    request = st.session_state.get("reportes_solicitud")
    if not request:
        st.info(
            "Seleccione el reporte y el rango de fechas en la barra lateral izquierda, "
            "luego presione Generar reporte."
        )
        section_title("Reportes disponibles")
        st.markdown(
            """
            <div class="wally-card">
                <div class="wally-label">Reporte 1</div>
                <div class="wally-value" style="font-size:1.25rem">Resumen Ejecutivo</div>
                <div class="wally-delta wally-muted">
                    KPIs de ventas, resumen por sucursal, desempeno por linea,
                    comparativos historicos, tendencia diaria y rotacion por embarque.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    report_name = request["name"]
    start_date = request["start"]
    end_date = request["end"]
    if (end_date - start_date) > timedelta(days=366):
        st.warning("El rango supera un ano; las tablas historicas pueden tardar mas en generarse.")

    st.markdown(
        f"**Reporte:** {report_name} &nbsp; | &nbsp; "
        f"**Periodo:** {start_date:%d/%m/%Y} al {end_date:%d/%m/%Y}"
    )
    try:
        with st.spinner(f"Generando {report_name}..."):
            report = _load_executive_report(start_date, end_date)
    except Exception as exc:
        st.error("No se pudo generar el Resumen Ejecutivo.")
        st.exception(exc)
        return

    if report["summary"].empty:
        st.info("No hay datos para el rango seleccionado.")
        return

    section_title("KPIs Ventas")
    _render_kpis(report["summary"])
    code_footer(*get_code("dashboard", "report"))

    section_title("Resumen por Sucursal")
    st.markdown(_render_branch_table(report["branch_kpis"]), unsafe_allow_html=True)
    code_footer(*get_code("dashboard", "branch_table"))

    section_title("Analisis de Desempeno Comercial por Linea")
    render_line_performance_table(report["line_performance"])
    code_footer(*get_code("gerencia", "line_performance"))

    section_title("Comparativo 4 Anios Rango Fecha")
    render_branch_range_comparison_table(report["branch_comparison"], report["branch_years"])
    code_footer(*get_code("gerencia", "range_year_table"))

    section_title("Tendencia de Facturacion por Dia")
    render_daily_comparison_table(report["daily"], report["daily_years"])
    code_footer(*get_code("gerencia", "day_table"))

    section_title("Rotacion por Embarque")
    render_shipment_summary_table(report["shipments"])
    code_footer(*get_code("existencias", "shipment_table"))

    sections = _export_sections(report)
    export_columns = st.columns(2)
    with export_columns[0]:
        st.download_button(
            "Exportar Resumen Ejecutivo a Excel",
            executive_report_to_excel_bytes(sections, start_date, end_date),
            file_name=export_filename("wally_resumen_ejecutivo", "xlsx"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with export_columns[1]:
        st.download_button(
            "Exportar Resumen Ejecutivo a PDF",
            executive_report_to_pdf_bytes(sections, start_date, end_date),
            file_name=export_filename("wally_resumen_ejecutivo", "pdf"),
            mime="application/pdf",
            use_container_width=True,
        )
