from __future__ import annotations

import plotly.express as px
import streamlit as st
import pandas as pd

from services import db
from services.charts import WALLY_COLORS, horizontal_bar_layout
from services.catalog import get_code
from services.exports import dataframe_to_excel_bytes, export_filename
from services.filters import date_sidebar, optional_multiselect
from services.formatting import money, number
from services.inventory_summary import resumen_embarque
from services.report_controls import color_picker, top_n_control
from services.ui import code_footer, display_compact_table, display_table, metric_card, page_title, section_title


def _ensure_columns(data: pd.DataFrame, defaults: dict) -> pd.DataFrame:
    for column, default in defaults.items():
        if column not in data.columns:
            data[column] = default
    return data


def _where(filters: dict[str, list[str]]) -> str:
    clauses = []
    for column, values in filters.items():
        if values:
            clauses.append(f"{column} IN ({db.sql_literal_list(values)})")
    return " AND ".join(clauses) if clauses else "1=1"


def render() -> None:
    page_title("Embarques y Coleccion", "Venta por embarque y coleccion")
    code_footer(*get_code("embarques", "report"))

    start_date, end_date = date_sidebar()
    start, end = db.date_params(start_date, end_date)
    rango_fecha = f"Fecha >= '{start}' AND Fecha < DATEADD(day, 1, '{end}')"
    try:
        sucursales = optional_multiselect("Sucursal", db.distinct_values(db.VIEW_VENTAS, "Sucursal", where=rango_fecha))
        lineas = optional_multiselect("Linea", db.distinct_values(db.VIEW_VENTAS, "Linea", where=rango_fecha))
        tipos = optional_multiselect("Tipo prenda", db.distinct_values(db.VIEW_VENTAS, "DescripTipoPrenda", where=rango_fecha))
    except Exception as exc:
        st.error("No se pudieron cargar filtros de embarques y coleccion.")
        st.exception(exc)
        return

    st.sidebar.markdown("### Personalizacion")
    top_n = top_n_control(default=12, max_value=50)
    color = color_picker()

    where_extra = _where({"Sucursal": sucursales, "Linea": lineas, "DescripTipoPrenda": tipos})

    try:
        data = db.read_sql(
            f"""
            WITH Ventas AS
            (
                SELECT
                    Sucursal,
                    CodEmbarqueAbreviado,
                    Coleccion_EN,
                    SUM(ISNULL(Unidades, 0)) AS Unidades,
                    SUM(ISNULL(VentaNetaQ, 0)) AS VentaNetaQ,
                    COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END) AS Facturas,
                    SUM(ISNULL(VentaNetaQ, 0)) - SUM(ISNULL(CostoTotal, 0)) AS MargenQ
                FROM {db.VIEW_VENTAS}
                WHERE Fecha >= ? AND Fecha < DATEADD(day, 1, ?)
                  AND {where_extra}
                  AND CodEmbarqueAbreviado IS NOT NULL
                GROUP BY Sucursal, CodEmbarqueAbreviado, Coleccion_EN
            ),
            Entradas AS
            (
                SELECT
                    Sucursal,
                    CodEmbarqueAbreviado,
                    SUM(UnidadesEntrada) AS UnidadesEntrada,
                    MIN(FechaEntrada) AS FechaPrimeraEntrada
                FROM {db.VIEW_ENTRADAS}
                GROUP BY Sucursal, CodEmbarqueAbreviado
            )
            SELECT
                v.Sucursal,
                v.CodEmbarqueAbreviado,
                v.Coleccion_EN,
                v.Unidades,
                v.VentaNetaQ,
                v.Facturas,
                v.MargenQ,
                ISNULL(e.UnidadesEntrada, 0) AS UnidadesEntrada,
                CAST(DATEDIFF(DAY, e.FechaPrimeraEntrada, CAST(GETDATE() AS date)) AS int) AS TVida,
                CASE
                    WHEN ISNULL(e.UnidadesEntrada, 0) = 0 THEN 0
                    ELSE CAST(v.Unidades AS decimal(18, 4)) / NULLIF(e.UnidadesEntrada, 0)
                END AS PorcRotacion
            FROM Ventas v
            LEFT JOIN Entradas e
                ON v.Sucursal = e.Sucursal
               AND v.CodEmbarqueAbreviado = e.CodEmbarqueAbreviado
            ORDER BY v.VentaNetaQ DESC
            """,
            (start, end),
        )
    except Exception as exc:
        st.error("No se pudo cargar la informacion de embarques y coleccion.")
        st.exception(exc)
        return

    data = _ensure_columns(
        data,
        {
            "Sucursal": "",
            "CodEmbarqueAbreviado": "",
            "Coleccion_EN": "",
            "Unidades": 0,
            "VentaNetaQ": 0,
            "Facturas": 0,
            "MargenQ": 0,
            "UnidadesEntrada": 0,
            "TVida": 0,
            "PorcRotacion": 0,
        },
    )

    if data.empty:
        st.info("No hay datos de embarques y coleccion para los filtros seleccionados.")
        return

    cols = st.columns(5)
    with cols[0]:
        metric_card("Venta Neta Q", money(data["VentaNetaQ"].sum()))
    with cols[1]:
        metric_card("Unidades", number(data["Unidades"].sum()))
    with cols[2]:
        metric_card("Facturas", number(data["Facturas"].sum()))
    with cols[3]:
        metric_card("Embarques", number(data["CodEmbarqueAbreviado"].nunique()))
    with cols[4]:
        metric_card("Colecciones", number(data["Coleccion_EN"].nunique()))

    by_embarque = (
        data.groupby("CodEmbarqueAbreviado", as_index=False)
        .agg(
            Unidades=("Unidades", "sum"),
            VentaNetaQ=("VentaNetaQ", "sum"),
            UnidadesEntrada=("UnidadesEntrada", "sum"),
            TVida=("TVida", "max"),
        )
        .sort_values("VentaNetaQ", ascending=False)
    )
    by_embarque["PorcRotacion"] = by_embarque["Unidades"] / by_embarque["UnidadesEntrada"].replace({0: pd.NA})
    by_embarque_chart = by_embarque.head(top_n)
    by_coleccion = (
        data.groupby("Coleccion_EN", as_index=False)
        .agg(Unidades=("Unidades", "sum"), VentaNetaQ=("VentaNetaQ", "sum"))
        .sort_values("VentaNetaQ", ascending=False)
    )
    by_coleccion_chart = by_coleccion.head(top_n)

    cols = st.columns(2)
    with cols[0]:
        section_title("Venta Neta Q por Embarque")
        fig = px.bar(
            by_embarque_chart.sort_values("VentaNetaQ"),
            x="VentaNetaQ",
            y="CodEmbarqueAbreviado",
            orientation="h",
            text="VentaNetaQ",
            color_discrete_sequence=[color],
        )
        fig.update_traces(texttemplate="Q %{text:,.0f}")
        st.plotly_chart(horizontal_bar_layout(fig, 430), use_container_width=True)
        code_footer(*get_code("embarques", "embarque_chart"))

    with cols[1]:
        section_title("Venta Neta Q por Coleccion_EN")
        fig = px.bar(
            by_coleccion_chart.sort_values("VentaNetaQ"),
            x="VentaNetaQ",
            y="Coleccion_EN",
            orientation="h",
            text="VentaNetaQ",
            color_discrete_sequence=[WALLY_COLORS[0]],
        )
        fig.update_traces(texttemplate="Q %{text:,.0f}")
        st.plotly_chart(horizontal_bar_layout(fig, 430), use_container_width=True)
        code_footer(*get_code("embarques", "coleccion_chart"))

    cols = st.columns(2)
    with cols[0]:
        section_title("Tabla por Embarque")
        tabla_embarque = by_embarque.rename(
            columns={
                "CodEmbarqueAbreviado": "Embarque",
                "VentaNetaQ": "Venta Q",
                "UnidadesEntrada": "Unid. Entrada",
                "TVida": "TVida",
                "PorcRotacion": "% Rotacion",
            }
        )
        display_table(tabla_embarque, height=360)
        code_footer(*get_code("embarques", "detail_table"))
    with cols[1]:
        section_title("Tabla por Coleccion")
        tabla_coleccion = by_coleccion.rename(columns={"Coleccion_EN": "Coleccion", "VentaNetaQ": "Venta Q"})
        display_table(tabla_coleccion, height=360)
        code_footer(*get_code("embarques", "detail_table"))

    try:
        existencia_data = db.read_sql(
            f"""
            WITH Existencia AS
            (
                SELECT
                    Sucursal,
                    NombreTallaColor,
                    CodEmbarqueAbreviado AS Embarque,
                    TVida,
                    SUM(ExistenciaFisica) AS ExistFisica
                FROM {db.VIEW_EXISTENCIA}
                GROUP BY Sucursal, NombreTallaColor, CodEmbarqueAbreviado, TVida
            ),
            Entradas AS
            (
                SELECT
                    Sucursal,
                    NombreTallaColor,
                    SUM(UnidadesEntrada) AS Entradas
                FROM {db.VIEW_ENTRADAS}
                GROUP BY Sucursal, NombreTallaColor
            ),
            Facturacion AS
            (
                SELECT
                    Sucursal,
                    NombreTallaColor,
                    SUM(Unidades) AS UnidFact
                FROM {db.VIEW_VENTAS}
                WHERE Trn = 'FV'
                GROUP BY Sucursal, NombreTallaColor
            )
            SELECT
                e.Sucursal,
                e.NombreTallaColor,
                e.Embarque,
                e.TVida,
                e.ExistFisica,
                ISNULL(en.Entradas, 0) AS Entradas,
                ISNULL(f.UnidFact, 0) AS UnidFact
            FROM Existencia e
            LEFT JOIN Entradas en
                ON e.Sucursal = en.Sucursal
               AND e.NombreTallaColor = en.NombreTallaColor
            LEFT JOIN Facturacion f
                ON e.Sucursal = f.Sucursal
               AND e.NombreTallaColor = f.NombreTallaColor
            WHERE e.Embarque IS NOT NULL
            """
        )
        existencia_data = _ensure_columns(
            existencia_data,
            {"Embarque": "", "TVida": 0, "ExistFisica": 0, "Entradas": 0, "UnidFact": 0},
        )
        section_title("Resumen por Embarque")
        shipment_table = resumen_embarque(existencia_data)
        display_compact_table(shipment_table)
        code_footer(*get_code("existencias", "shipment_table"))
    except Exception as exc:
        st.error("No se pudo cargar el resumen de existencias por embarque.")
        st.exception(exc)
    st.download_button(
        "Exportar embarques y coleccion a Excel",
        dataframe_to_excel_bytes(
            {
                "Detalle": data,
                "Por Embarque": by_embarque,
                "Por Coleccion": by_coleccion,
            }
        ),
        file_name=export_filename("wally_embarques_coleccion"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
