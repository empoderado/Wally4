from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st
from services.filters import optional_multiselect

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
from services.exports import export_filename, dataframe_to_excel_bytes
from services.formatting import money, number, percent
from services.ui import code_footer, metric_card, section_title
from services.charts import build_branch_chart, build_line_chart, build_daily_chart



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
            SUM(ISNULL(VentaNetaQ, 0)) / 1.12 - SUM(ISNULL(CostoTotal, 0)) AS MargenQ
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
            SUM(ISNULL(VentaNetaQ, 0)) / 1.12 - SUM(ISNULL(CostoTotal, 0)) AS MargenQ
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
            {"Indicador": "% Margen", "Valor": margen / (venta / 1.12) if venta else 0},
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
        ("Margen", money(margen), percent(margen / (venta / 1.12) if venta else 0), margen >= 0),
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


def _load_stock_and_sales(start_date: date, end_date: date, detailed: bool) -> pd.DataFrame:
    start, end = db.date_params(start_date, end_date)
    
    query = """
    WITH CombinedKeys AS (
        SELECT Sucursal, Referencia, NombreTallaColor, Talla, Color, Linea, CodEmbarqueAbreviado AS Embarque
        FROM dbo.VwExistencia
        UNION
        SELECT Sucursal, Referencia, NombreTallaColor, Talla, Color, Linea, CodEmbarqueAbreviado AS Embarque
        FROM dbo.VwFacturaConImpuesto
        WHERE Fecha >= ? AND Fecha < DATEADD(day, 1, ?)
        UNION
        SELECT Sucursal, Referencia, NombreTallaColor, Talla, Color, Linea, CodEmbarqueAbreviado AS Embarque
        FROM dbo.VwEntradasInventario
    ),
    KeysWithAttributes AS (
        SELECT 
            k.Sucursal,
            k.Referencia,
            k.NombreTallaColor,
            k.Talla,
            k.Color,
            k.Linea AS LineaOriginal,
            COALESCE(e.Descripcion3Linea, f.Descripcion3Tabla4, k.Linea) AS Linea,
            COALESCE(e.DescSubLinea, f.DescSubLinea) AS Sublinea,
            k.Embarque,
            COALESCE(
                e.TVida,
                (SELECT DATEDIFF(day, MIN(FechaEntrada), GETDATE()) FROM dbo.VwEntradasInventario WHERE CodEmbarqueAbreviado = k.Embarque)
            ) AS TVida
        FROM CombinedKeys k
        LEFT JOIN dbo.VwExistencia e 
            ON k.Sucursal = e.Sucursal 
           AND k.NombreTallaColor = e.NombreTallaColor
        LEFT JOIN (
            SELECT DISTINCT Sucursal, NombreTallaColor, Descripcion3Tabla4, DescSubLinea
            FROM dbo.VwFacturaConImpuesto
        ) f
            ON k.Sucursal = f.Sucursal
           AND k.NombreTallaColor = f.NombreTallaColor
    ),
    ExistenciaAgg AS (
        SELECT Sucursal, NombreTallaColor, SUM(ExistenciaFisica) AS ExistFisica, SUM(ExistenciaDisponible) AS ExistDisp
        FROM dbo.VwExistencia
        GROUP BY Sucursal, NombreTallaColor
    ),
    EntradasAgg AS (
        SELECT Sucursal, NombreTallaColor, SUM(UnidadesEntrada) AS Entradas
        FROM dbo.VwEntradasInventario
        GROUP BY Sucursal, NombreTallaColor
    ),
    VentasAgg AS (
        SELECT 
            Sucursal, 
            NombreTallaColor, 
            SUM(
                CASE 
                    WHEN Trn = 'FV' THEN ISNULL(Unidades, 0)
                    WHEN Trn IN ('NC', 'NCC') THEN -ABS(ISNULL(Unidades, 0))
                    ELSE 0 
                END
            ) AS UnidFact,
            SUM(
                CASE 
                    WHEN Trn = 'FV' THEN ISNULL(DescuentoValor, 0)
                    WHEN Trn IN ('NC', 'NCC') THEN -ABS(ISNULL(DescuentoValor, 0))
                    ELSE 0 
                END
            ) AS DescuentoQ,
            SUM(
                CASE 
                    WHEN Trn = 'FV' THEN ISNULL(VentaBruta, 0)
                    WHEN Trn IN ('NC', 'NCC') THEN -ABS(ISNULL(VentaBruta, 0))
                    ELSE 0 
                END
            ) AS VentaBruta
        FROM dbo.VwFacturaConImpuesto
        WHERE Trn IN ('FV', 'NC', 'NCC') AND Fecha >= ? AND Fecha < DATEADD(day, 1, ?)
        GROUP BY Sucursal, NombreTallaColor
    ),
    ActivePromotions AS (
        SELECT 
            pa.Codigo AS ItemCodigo,
            p.Descripcion AS PromocionNombre,
            p.Valor AS PromocionValor,
            ROW_NUMBER() OVER (PARTITION BY pa.Codigo ORDER BY p.Valor DESC, p.idPromocion DESC) AS rn
        FROM StudioF.dbo.PromocionArticuloAplica pa
        INNER JOIN StudioF.dbo.Promocion p ON pa.idPromocion = p.idPromocion
        WHERE p.FlagActivo = 1 
          AND GETDATE() >= p.FechaInicia 
          AND GETDATE() <= p.FechaFin
    )
    SELECT 
        k.Sucursal,
        k.Referencia,
        k.Linea,
        k.Sublinea,
        k.Talla,
        k.Color,
        k.Embarque,
        k.TVida,
        k.LineaOriginal,
        ISNULL(ex.ExistFisica, 0) AS ExistFisica,
        ISNULL(ex.ExistDisp, 0) AS ExistDisp,
        ISNULL(en.Entradas, 0) AS Entradas,
        ISNULL(v.UnidFact, 0) AS UnidFact,
        ISNULL(COALESCE(ap_det.PromocionValor, ap_ref.PromocionValor, 0), 0) AS DescuentoPct,
        COALESCE(ap_det.PromocionNombre, ap_ref.PromocionNombre, 'Precio Regular') AS PromocionNombre
    FROM KeysWithAttributes k
    LEFT JOIN ExistenciaAgg ex ON k.Sucursal = ex.Sucursal AND k.NombreTallaColor = ex.NombreTallaColor
    LEFT JOIN EntradasAgg en ON k.Sucursal = en.Sucursal AND k.NombreTallaColor = en.NombreTallaColor
    LEFT JOIN VentasAgg v ON k.Sucursal = v.Sucursal AND k.NombreTallaColor = v.NombreTallaColor
    LEFT JOIN ActivePromotions ap_det ON k.NombreTallaColor = ap_det.ItemCodigo COLLATE database_default AND ap_det.rn = 1
    LEFT JOIN ActivePromotions ap_ref ON k.Referencia = ap_ref.ItemCodigo COLLATE database_default AND ap_ref.rn = 1
    """
    
    df = db.read_sql(query, (start, end, start, end))
    if df.empty:
        return df

    def get_rango_tvida(tvida):
        if pd.isna(tvida) or tvida is None:
            return "366 en adelante"
        try:
            val = int(tvida)
        except Exception:
            return "366 en adelante"
        if val <= 30:
            return "0 a 30"
        elif val <= 60:
            return "31 a 60"
        elif val <= 90:
            return "61 a 90"
        elif val <= 120:
            return "91 a 120"
        elif val <= 150:
            return "121 a 150"
        elif val <= 180:
            return "151 a 180"
        elif val <= 240:
            return "181 a 240"
        elif val <= 300:
            return "241 a 300"
        elif val <= 365:
            return "301 a 365"
        else:
            return "366 en adelante"

    if detailed:
        df["TVida"] = df["TVida"].fillna(366).astype(int)
        df["RangoTvida"] = df["TVida"].apply(get_rango_tvida)
        df["ExistFisica"] = df["ExistFisica"].astype(int)
        df["ExistDisp"] = df["ExistDisp"].astype(int)
        df["Entradas"] = df["Entradas"].astype(int)
        df["UnidFact"] = df["UnidFact"].astype(int)
        df["%Rot"] = df.apply(lambda r: r["UnidFact"] / r["Entradas"] if r["Entradas"] > 0 else 0.0, axis=1)
        df["Descuento"] = df.apply(lambda r: f"{r['DescuentoPct']:.1f}%" if r['DescuentoPct'] > 0 else "0%", axis=1)
        df["RangoTvida "] = df["RangoTvida"]
        
        cols = [
            "Sucursal", "Referencia", "Linea", "Sublinea", "Talla", "Color", 
            "Embarque", "TVida", "RangoTvida", "ExistFisica", "ExistDisp", 
            "Entradas", "UnidFact", "%Rot", "LineaOriginal", "Descuento", "PromocionNombre", "RangoTvida "
        ]
        df = df[cols]
        df = df.rename(columns={"PromocionNombre": "Promocion"})
    else:
        df["TVida"] = df["TVida"].fillna(366).astype(int)
        df["ExistFisica"] = df["ExistFisica"].astype(int)
        df["ExistDisp"] = df["ExistDisp"].astype(int)
        df["Entradas"] = df["Entradas"].astype(int)
        df["UnidFact"] = df["UnidFact"].astype(int)
        df["DescuentoPct"] = df["DescuentoPct"].astype(float)
        
        grouped = df.groupby(
            ["Sucursal", "Referencia", "Linea", "Sublinea", "Embarque", "LineaOriginal"],
            as_index=False
        ).agg({
            "TVida": "max",
            "ExistFisica": "sum",
            "ExistDisp": "sum",
            "Entradas": "sum",
            "UnidFact": "sum",
            "DescuentoPct": "max",
            "PromocionNombre": "first"
        })
        
        grouped["RangoTvida"] = grouped["TVida"].apply(get_rango_tvida)
        grouped["%Rot"] = grouped.apply(lambda r: r["UnidFact"] / r["Entradas"] if r["Entradas"] > 0 else 0.0, axis=1)
        grouped["Descuento"] = grouped.apply(lambda r: f"{r['DescuentoPct']:.1f}%" if r['DescuentoPct'] > 0 else "0%", axis=1)
        grouped["RangoTvida "] = grouped["RangoTvida"]
        
        cols = [
            "Sucursal", "Referencia", "Linea", "Sublinea", 
            "Embarque", "TVida", "RangoTvida", "ExistFisica", "ExistDisp", 
            "Entradas", "UnidFact", "%Rot", "LineaOriginal", "Descuento", "PromocionNombre", "RangoTvida "
        ]
        df = grouped[cols]
        df = df.rename(columns={"PromocionNombre": "Promocion"})

    return df


def render() -> None:
    _branch_table_css()
    _report_heading()
    default_start, default_end = _default_dates()
    st.sidebar.markdown("### Generacion de reportes")
    report_name = st.sidebar.selectbox(
        "Reporte",
        ["Resumen Ejecutivo", "Stock Y Ventas"],
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
    modalidad = "Detallado"
    if report_name == "Stock Y Ventas":
        modalidad = st.sidebar.radio(
            "Detalle",
            ["Detallado", "Agrupado por Referencia"],
            key="reportes_modalidad",
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
                "modalidad": modalidad,
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
            <div class="wally-card" style="margin-top: 15px">
                <div class="wally-label">Reporte 2</div>
                <div class="wally-value" style="font-size:1.25rem">Stock Y Ventas</div>
                <div class="wally-delta wally-muted">
                    Existencias físicas y disponibles, entradas, ventas, rotación, antigüedad de embarque y descuentos del ERP Smartbit por referencia.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    report_name = request["name"]
    start_date = request["start"]
    end_date = request["end"]
    modalidad = request.get("modalidad", "Detallado")

    if report_name == "Stock Y Ventas":
        st.markdown(
            f"**Reporte:** {report_name} ({modalidad}) &nbsp; | &nbsp; "
            f"**Periodo:** {start_date:%d/%m/%Y} al {end_date:%d/%m/%Y}"
        )
        try:
            with st.spinner("Generando Stock Y Ventas..."):
                data = _load_stock_and_sales(start_date, end_date, modalidad == "Detallado")
        except Exception as exc:
            st.error("No se pudo generar el reporte Stock Y Ventas.")
            st.exception(exc)
            return

        if data.empty:
            st.info("No hay datos para el rango seleccionado.")
            return

        section_title(f"Stock Y Ventas - {modalidad}")
        st.dataframe(data, use_container_width=True)

        st.download_button(
            "Exportar Stock Y Ventas a Excel",
            dataframe_to_excel_bytes({"Stock Y Ventas": data}),
            file_name=export_filename("wally_stock_y_ventas", "xlsx"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        return
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
    st.plotly_chart(build_branch_chart(report["branch_kpis"], height=300), use_container_width=True, key="report_branch_chart")
    code_footer(*get_code("dashboard", "branch_table"))

    section_title("Analisis de Desempeno Comercial por Linea")
    render_line_performance_table(report["line_performance"])
    st.plotly_chart(build_line_chart(report["line_performance"], height=300), use_container_width=True, key="report_line_chart")
    code_footer(*get_code("gerencia", "line_performance"))

    section_title("Comparativo 4 Anios Rango Fecha")
    render_branch_range_comparison_table(report["branch_comparison"], report["branch_years"])
    code_footer(*get_code("gerencia", "range_year_table"))

    section_title("Tendencia de Facturacion por Dia")
    render_daily_comparison_table(report["daily"], report["daily_years"])
    st.plotly_chart(build_daily_chart(report["daily"], report.get("daily_years"), height=300), use_container_width=True, key="report_daily_chart")
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
