from __future__ import annotations

import pandas as pd
import streamlit as st

from services import db
from services.catalog import get_code
from services.exports import dataframe_to_excel_bytes, export_filename
from services.filters import date_sidebar, optional_multiselect
from services.formatting import number
from services.inventory_summary import resumen_embarque
from services.report_controls import chart_type_control, color_picker, dimension_control, metric_control, render_custom_chart, top_n_control
from services.ui import code_footer, display_table, filter_dataframe, metric_card, page_title, section_title


def _ensure_columns(data, defaults):
    for column, default in defaults.items():
        if column not in data.columns:
            data[column] = default
    return data


def _view_columns(view_name: str) -> set[str]:
    try:
        sample = db.read_sql(f"SELECT TOP 0 * FROM {view_name}")
        return set(sample.columns)
    except Exception:
        return set()


def _line_group_expr(view_name: str) -> str:
    columns = _view_columns(view_name)
    if "Descripcion3Tabla4" in columns:
        return "UPPER(LTRIM(RTRIM(CAST(COALESCE(NULLIF(Descripcion3Tabla4, ''), Linea) AS varchar(250)))))"
    return "UPPER(LTRIM(RTRIM(CAST(Linea AS varchar(250)))))"


def _line_group_mapping(start_date, end_date) -> dict[str, str]:
    sales_expr = _line_group_expr(db.VIEW_VENTAS)
    frames = []
    try:
        frames.append(
            db.read_sql(
                f"""
                SELECT DISTINCT
                    UPPER(LTRIM(RTRIM(CAST(Linea AS varchar(250))))) AS LineaOriginal,
                    {sales_expr} AS LineaAgrupada
                FROM {db.VIEW_VENTAS}
                WHERE Fecha >= ? AND Fecha < DATEADD(day, 1, ?)
                  AND Linea IS NOT NULL
                  AND LTRIM(RTRIM(CAST(Linea AS varchar(250)))) <> ''
                """,
                db.date_params(start_date, end_date),
            )
        )
    except Exception:
        pass
    try:
        frames.append(
            db.read_sql(
                f"""
                SELECT DISTINCT
                    UPPER(LTRIM(RTRIM(CAST(Linea AS varchar(250))))) AS LineaOriginal,
                    {sales_expr} AS LineaAgrupada
                FROM {db.VIEW_VENTAS}
                WHERE Linea IS NOT NULL
                  AND LTRIM(RTRIM(CAST(Linea AS varchar(250)))) <> ''
                """
            )
        )
    except Exception:
        pass
    if not frames:
        return {}
    mapping = pd.concat(frames, ignore_index=True)
    if mapping.empty or "LineaOriginal" not in mapping.columns or "LineaAgrupada" not in mapping.columns:
        return {}
    mapping["LineaOriginal"] = mapping["LineaOriginal"].astype(str).str.strip().str.upper()
    mapping["LineaAgrupada"] = mapping["LineaAgrupada"].astype(str).str.strip().str.upper()
    mapping = mapping[(mapping["LineaOriginal"] != "") & (mapping["LineaAgrupada"] != "")]
    return dict(mapping.drop_duplicates("LineaOriginal")[["LineaOriginal", "LineaAgrupada"]].values)


def _group_line_value(value, mapping: dict[str, str]) -> str:
    normalized = str(value or "").strip().upper()
    return mapping.get(normalized, normalized)


def render() -> None:
    page_title("Existencias", "Inventario fisico y disponible por sucursal, referencia, talla, color y embarque")
    code_footer(*get_code("existencias", "report"))
    start_date, end_date = date_sidebar()
    st.sidebar.markdown("### Filtros de existencia")
    try:
        line_group_map = _line_group_mapping(start_date, end_date)
        sucursales = optional_multiselect("Sucursal", db.distinct_values(db.VIEW_EXISTENCIA, "Sucursal"))
        raw_lineas = db.distinct_values(db.VIEW_EXISTENCIA, "Linea")
        grouped_lineas = sorted({_group_line_value(value, line_group_map) for value in raw_lineas if str(value).strip()})
        lineas = optional_multiselect("Linea", grouped_lineas)
        embarques = optional_multiselect("Embarque", db.distinct_values(db.VIEW_EXISTENCIA, "CodEmbarqueAbreviado"))
    except Exception as exc:
        st.error("No se pudieron cargar filtros de existencia.")
        st.exception(exc)
        return
    st.sidebar.markdown("### Personalización")
    dimension = dimension_control(["Sucursal", "Linea", "Embarque", "Referencia"], "Sucursal")
    metric = metric_control(["ExistDisp", "ExistFisica", "Entradas", "UnidFact", "%Rot", "TVida"], "ExistDisp")
    chart_type = chart_type_control("Barras verticales", ["Barras horizontales", "Barras verticales", "Dona"])
    custom_color = color_picker()
    top_n = top_n_control(default=15, max_value=50)

    clauses = []
    if sucursales:
        clauses.append(f"Sucursal IN ({db.sql_literal_list(sucursales)})")
    if embarques:
        clauses.append(f"CodEmbarqueAbreviado IN ({db.sql_literal_list(embarques)})")
    consulta_referencia = st.text_input(
        "Consultar existencia por referencia",
        placeholder="Escriba una referencia, por ejemplo DFS740180A",
    )
    if consulta_referencia:
        safe_ref = consulta_referencia.replace("'", "''")
        clauses.append(f"(Referencia LIKE '%{safe_ref}%' OR NombreTallaColor LIKE '%{safe_ref}%')")
    where = " AND ".join(clauses) if clauses else "1=1"
    try:
        data = db.read_sql(
            f"""
            WITH Existencia AS
            (
                SELECT
                    Sucursal,
                    Referencia,
                    NombreTallaColor,
                    Talla,
                    Color,
                    Linea,
                    DescSubLinea AS Sublinea,
                    CodEmbarqueAbreviado,
                    TVida,
                    SUM(ExistenciaFisica) AS ExistenciaFisica,
                    SUM(ExistenciaDisponible) AS ExistenciaDisponible
                FROM {db.VIEW_EXISTENCIA}
                WHERE {where}
                GROUP BY Sucursal, Referencia, NombreTallaColor, Talla, Color, Linea, DescSubLinea, CodEmbarqueAbreviado, TVida
            ),
            Entradas AS
            (
                SELECT
                    Sucursal,
                    NombreTallaColor,
                    SUM(UnidadesEntrada) AS UnidadesEntrada
                FROM {db.VIEW_ENTRADAS}
                GROUP BY Sucursal, NombreTallaColor
            ),
            Facturacion AS
            (
                SELECT
                    Sucursal,
                    NombreTallaColor,
                    SUM(Unidades) AS UnidadesFacturadas
                FROM {db.VIEW_VENTAS}
                WHERE Trn = 'FV'
                GROUP BY Sucursal, NombreTallaColor
            )
            SELECT
                e.Sucursal,
                e.Referencia,
                e.Linea,
                e.Sublinea,
                e.Talla,
                e.Color,
                e.CodEmbarqueAbreviado AS Embarque,
                e.TVida,
                e.ExistenciaFisica AS ExistFisica,
                e.ExistenciaDisponible AS ExistDisp,
                ISNULL(en.UnidadesEntrada, 0) AS Entradas,
                ISNULL(f.UnidadesFacturadas, 0) AS UnidFact,
                CASE
                    WHEN ISNULL(en.UnidadesEntrada, 0) = 0 THEN 0
                    ELSE CAST(ISNULL(f.UnidadesFacturadas, 0) AS decimal(18, 4)) / NULLIF(en.UnidadesEntrada, 0)
                END AS [%Rot]
            FROM Existencia e
            LEFT JOIN Entradas en
                ON e.Sucursal = en.Sucursal
               AND e.NombreTallaColor = en.NombreTallaColor
            LEFT JOIN Facturacion f
                ON e.Sucursal = f.Sucursal
               AND e.NombreTallaColor = f.NombreTallaColor
            ORDER BY e.TVida ASC, e.CodEmbarqueAbreviado ASC, e.ExistenciaDisponible DESC
            """,
        )
    except Exception as exc:
        st.error("No se pudo cargar existencia.")
        st.exception(exc)
        return

    data = _ensure_columns(
        data,
        {
            "Sucursal": "",
            "Referencia": "",
            "Linea": "",
            "Sublinea": "",
            "Talla": "",
            "Color": "",
            "Embarque": "",
            "TVida": 0,
            "ExistFisica": 0,
            "ExistDisp": 0,
            "Entradas": 0,
            "UnidFact": 0,
            "%Rot": 0,
        },
    )
    if "Linea" in data.columns:
        data["LineaOriginal"] = data["Linea"].astype(str).str.strip().str.upper()
        data["Linea"] = data["LineaOriginal"].map(lambda value: _group_line_value(value, line_group_map))
    if lineas:
        selected_lines = {str(value).strip().upper() for value in lineas}
        data = data[data["Linea"].astype(str).str.upper().isin(selected_lines)].reset_index(drop=True)

    if data.empty:
        st.info("No hay existencia con los filtros seleccionados.")
        return

    section_title("Detalle de Existencias")
    table_data = data.copy()
    table_data = filter_dataframe(
        table_data,
        "t_exi_01",
        ["Sucursal", "Referencia", "Linea", "Talla", "Color", "Embarque"],
    )
    detail_columns = [
        "Sucursal",
        "Referencia",
        "Linea",
        "Color",
        "Talla",
        "ExistFisica",
        "ExistDisp",
        "Embarque",
        "TVida",
        "Entradas",
        "UnidFact",
        "%Rot",
    ]
    detail_data = table_data[detail_columns].rename(
        columns={
            "ExistFisica": "Existencia Fisica",
            "ExistDisp": "Existencia Disponible",
        }
    )
    display_table(detail_data, height=470, highlight_zero_columns=["Existencia Disponible"])
    code_footer(*get_code("existencias", "detail_table"))
    if consulta_referencia and table_data["Referencia"].nunique() == 1:
        section_title("Imagenes del producto")
        from pathlib import Path

        image_dir = Path(r"D:\SmartBITSystems\Archivos\1\FotosArticulos")
        reference = str(table_data["Referencia"].dropna().iloc[0])
        images = []
        if image_dir.exists():
            for pattern in (f"*{reference}*.jpg", f"*{reference}*.jpeg", f"*{reference}*.png"):
                images.extend(image_dir.glob(pattern))
        images = sorted(
            images,
            key=lambda path: (
                0 if reference.upper() in path.stem.upper() else 1,
                path.name.upper(),
            ),
        )
        if images:
            cols = st.columns(4)
            for idx, image_path in enumerate(images[:4]):
                with cols[idx]:
                    st.image(str(image_path), use_column_width=True)
        else:
            st.info("No hay imagenes para esta referencia en D:\\SmartBITSystems\\Archivos\\1\\FotosArticulos.")

    cols = st.columns(4)
    with cols[0]:
        metric_card("Existencia Disponible", number(data["ExistDisp"].sum()))
    with cols[1]:
        metric_card("Existencia Fisica", number(data["ExistFisica"].sum()))
    with cols[2]:
        metric_card("Referencias", number(data["Referencia"].nunique()))
    with cols[3]:
        metric_card("Embarques", number(data["Embarque"].nunique()))

    section_title(f"{metric} por {dimension}")
    render_custom_chart(data, dimension, metric, chart_type, custom_color, top_n, height=430)
    code_footer(*get_code("existencias", "main_chart"))

    cols = st.columns(2)
    with cols[0]:
        section_title("Existencia Fisica por Linea")
        render_custom_chart(data, "Linea", "ExistFisica", "Barras verticales", custom_color, top_n, height=390)
        code_footer(*get_code("existencias", "line_chart"))
    with cols[1]:
        section_title("Linea Jeans por Sublinea")
        jeans_data = data[data["Linea"].astype(str).str.upper().str.contains("JEAN", na=False)]
        render_custom_chart(jeans_data, "Sublinea", "ExistFisica", "Barras verticales", custom_color, top_n, height=390)
        code_footer(*get_code("existencias", "jeans_subline_chart"))

    shipment_table = resumen_embarque(data)
    st.download_button(
        "Exportar existencias a Excel",
        dataframe_to_excel_bytes({"Existencias": data, "Resumen por Embarque": shipment_table}),
        file_name=export_filename("wally_existencias"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
