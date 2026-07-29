from __future__ import annotations

import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

from services import db
from services.exports import export_filename, dataframe_to_excel_bytes
from services.filters import optional_multiselect
from services.ui import page_title, section_title, code_footer
from services.local_store import get_param
from services.catalog import get_code


def _load_rotacion_datos(lineas: list[str], embarques: list[str]) -> pd.DataFrame:
    clauses_ventas = ["1=1"]
    clauses_exist = ["1=1"]
    clauses_ent = ["1=1"]
    
    if lineas:
        lit_lineas = db.sql_literal_list(lineas)
        clauses_ventas.append(f"Linea IN ({lit_lineas})")
        clauses_exist.append(f"Linea IN ({lit_lineas})")
        clauses_ent.append(f"Linea IN ({lit_lineas})")
    if embarques:
        lit_embarques = db.sql_literal_list(embarques)
        clauses_ventas.append(f"CodEmbarqueAbreviado IN ({lit_embarques})")
        clauses_exist.append(f"CodEmbarqueAbreviado IN ({lit_embarques})")
        clauses_ent.append(f"CodEmbarqueAbreviado IN ({lit_embarques})")
        
    where_ventas = " AND ".join(clauses_ventas)
    where_exist = " AND ".join(clauses_exist)
    where_ent = " AND ".join(clauses_ent)
    
    query = f"""
    WITH EntradasRef AS (
        SELECT Referencia, SUM(UnidadesEntrada) AS Entradas, MIN(FechaEntrada) AS MinFechaEntrada
        FROM dbo.VwEntradasInventario
        WHERE {where_ent}
        GROUP BY Referencia
    ),
    ExistenciaRef AS (
        SELECT 
            Referencia, 
            MAX(DescripcionArticulo) AS Descripcion, 
            MAX(CodEmbarqueAbreviado) AS Embarque,
            SUM(ExistenciaFisica) AS InventarioActual
        FROM dbo.VwExistencia
        WHERE {where_exist}
        GROUP BY Referencia
    ),
    VentasAcum AS (
        SELECT Referencia, SUM(Unidades) AS VentasAcumuladas
        FROM dbo.VwFacturaConImpuesto
        WHERE Trn = 'FV' AND {where_ventas}
        GROUP BY Referencia
    ),
    VentasSemanas AS (
        SELECT 
            Referencia,
            SUM(CASE WHEN Fecha >= DATEADD(day, -7, CAST(GETDATE() AS DATE)) THEN Unidades ELSE 0 END) AS VentasSemana1,
            SUM(CASE WHEN Fecha >= DATEADD(day, -14, CAST(GETDATE() AS DATE)) AND Fecha < DATEADD(day, -7, CAST(GETDATE() AS DATE)) THEN Unidades ELSE 0 END) AS VentasSemana2,
            SUM(CASE WHEN Fecha >= DATEADD(day, -21, CAST(GETDATE() AS DATE)) AND Fecha < DATEADD(day, -14, CAST(GETDATE() AS DATE)) THEN Unidades ELSE 0 END) AS VentasSemana3,
            SUM(CASE WHEN Fecha >= DATEADD(day, -28, CAST(GETDATE() AS DATE)) AND Fecha < DATEADD(day, -21, CAST(GETDATE() AS DATE)) THEN Unidades ELSE 0 END) AS VentasSemana4
        FROM dbo.VwFacturaConImpuesto
        WHERE Trn = 'FV' AND {where_ventas}
        GROUP BY Referencia
    ),
    VentasIntervalos AS (
        SELECT 
            v.Referencia,
            SUM(CASE WHEN DATEDIFF(day, e.MinFechaEntrada, v.Fecha) BETWEEN 0 AND 3 THEN v.Unidades ELSE 0 END) AS Ventas_1_3,
            SUM(CASE WHEN DATEDIFF(day, e.MinFechaEntrada, v.Fecha) BETWEEN 4 AND 7 THEN v.Unidades ELSE 0 END) AS Ventas_4_7,
            SUM(CASE WHEN DATEDIFF(day, e.MinFechaEntrada, v.Fecha) BETWEEN 8 AND 12 THEN v.Unidades ELSE 0 END) AS Ventas_8_12
        FROM dbo.VwFacturaConImpuesto v
        INNER JOIN EntradasRef e ON v.Referencia = e.Referencia
        WHERE v.Trn = 'FV' AND {where_ventas}
        GROUP BY v.Referencia
    )
    SELECT 
        e.Referencia,
        COALESCE(x.Descripcion, '') AS Descripcion,
        COALESCE(x.Embarque, '') AS Embarque,
        ISNULL(e.Entradas, 0) AS Entradas,
        e.MinFechaEntrada,
        ISNULL(v.VentasAcumuladas, 0) AS VentasAcumuladas,
        ISNULL(x.InventarioActual, 0) AS InventarioActual,
        ISNULL(w.VentasSemana1, 0) AS VentasSemana1,
        ISNULL(w.VentasSemana2, 0) AS VentasSemana2,
        ISNULL(w.VentasSemana3, 0) AS VentasSemana3,
        ISNULL(w.VentasSemana4, 0) AS VentasSemana4,
        ISNULL(vi.Ventas_1_3, 0) AS Ventas_1_3,
        ISNULL(vi.Ventas_4_7, 0) AS Ventas_4_7,
        ISNULL(vi.Ventas_8_12, 0) AS Ventas_8_12
    FROM EntradasRef e
    INNER JOIN ExistenciaRef x ON e.Referencia = x.Referencia
    LEFT JOIN VentasAcum v ON e.Referencia = v.Referencia
    LEFT JOIN VentasSemanas w ON e.Referencia = w.Referencia
    LEFT JOIN VentasIntervalos vi ON e.Referencia = vi.Referencia
    WHERE e.Entradas > 0
      AND (x.InventarioActual > 0 OR w.VentasSemana1 > 0 OR w.VentasSemana2 > 0 OR w.VentasSemana3 > 0 OR w.VentasSemana4 > 0);
    """
    return db.read_sql(query, apply_branch_filter=False)


def _get_sorted_shipments() -> list[str]:
    query = """
    SELECT CodEmbarqueAbreviado AS Embarque, MAX(FechaEntrada) AS UltimaEntrada
    FROM dbo.VwEntradasInventario
    WHERE CodEmbarqueAbreviado IS NOT NULL AND LTRIM(RTRIM(CodEmbarqueAbreviado)) <> ''
    GROUP BY CodEmbarqueAbreviado
    ORDER BY UltimaEntrada DESC;
    """
    df = db.read_sql(query, apply_branch_filter=False)
    return df["Embarque"].dropna().tolist()


def render() -> None:
    page_title("Rotacion Derivada", "Clasificación comercial basada en velocidad, aceleración y stock remanente")
    
    def _make_sparkline_svg(values: list[int]) -> str:
        if not values or all(v == 0 for v in values):
            return "-"
        v_min = min(values)
        v_max = max(values)
        v_range = (v_max - v_min) if v_max > v_min else 1
        
        width = 60
        height = 18
        points = []
        for i, v in enumerate(values):
            x = int((i / (len(values) - 1)) * width)
            y = int(height - ((v - v_min) / v_range) * height)
            points.append(f"{x},{y}")
        
        points_str = " ".join(points)
        return f'<svg width="{width}" height="{height}" style="vertical-align: middle;"><polyline fill="none" stroke="#2563eb" stroke-width="2" points="{points_str}" /></svg>'

    try:
        shipments_list = _get_sorted_shipments()
    except Exception as exc:
        st.error("No se pudieron cargar los embarques desde la base de datos.")
        st.exception(exc)
        return
        
    if not shipments_list:
        st.warning("No hay embarques registrados en el sistema.")
        return

    # Dropdown at the top of the page, sorted from most recent to oldest
    selected_shipment = st.selectbox(
        "Seleccione el Embarque a Analizar",
        shipments_list,
        index=0,
        key="rot_selected_shipment"
    )
    
    # Render report code
    code_footer(*get_code("existencias", "rotacion_derivada"))
    
    # 1. Load configuration parameters from database (configured by admin)
    try:
        vel_t = float(get_param("rot_threshold_vel", "1.0"))
    except ValueError:
        vel_t = 1.0

    try:
        inv_t = int(get_param("rot_threshold_inv", "30"))
    except ValueError:
        inv_t = 30

    st.sidebar.markdown("### Filtros de Referencias")
    lineas = []
    try:
        lineas = optional_multiselect(
            "Línea", 
            db.distinct_values(db.VIEW_EXISTENCIA, "Linea"),
            key="rot_filtro_linea"
        )
    except Exception:
        st.sidebar.error("Error al cargar filtros de línea.")

    st.sidebar.caption("El análisis se actualiza automáticamente al seleccionar diferentes filtros.")

    st.markdown(
        f"**Umbral Velocidad:** {vel_t:.2f}% de entradas / día &nbsp; | &nbsp; "
        f"**Umbral Inventario Remanente:** {inv_t}% de entradas"
    )

    try:
        with st.spinner("Cargando y calculando rotación de referencias..."):
            df = _load_rotacion_datos(lineas, [selected_shipment])
    except Exception as exc:
        st.error("No se pudo obtener la información de rotación de la base de datos.")
        st.exception(exc)
        return

    if df.empty:
        st.warning(f"No se encontraron referencias activas para el embarque {selected_shipment} con los filtros seleccionados.")
        return

    df['Rotación: 1-3'] = df['Ventas_1_3'] / df['Entradas']
    df['Rotación: 4-7'] = df['Ventas_4_7'] / df['Entradas']
    df['Rotación: 8-12'] = df['Ventas_8_12'] / df['Entradas']
    df['Sell Through Acumulado (%)'] = df['VentasAcumuladas'] / df['Entradas']
    df['Velocidad Venta (% entradas/dia)'] = (df['VentasSemana1'] / 7.0) / df['Entradas'] * 100.0
    df['Velocidad Anterior'] = (df['VentasSemana2'] / 7.0) / df['Entradas'] * 100.0
    df['Aceleración (cambio de velocidad)'] = df['Velocidad Venta (% entradas/dia)'] - df['Velocidad Anterior']
    df['Cobertura (dias)'] = np.where(df['VentasSemana1'] > 0, df['InventarioActual'] / (df['VentasSemana1'] / 7.0), 999.0)
    df['Rotación (ventas / inv. promedio)'] = df['VentasAcumuladas'] / ((df['Entradas'] + df['InventarioActual']) / 2.0)
    
    # Calculate Tvida (days since MinFechaEntrada)
    df['MinFechaEntrada_dt'] = pd.to_datetime(df['MinFechaEntrada'], errors='coerce')
    today_dt = pd.Timestamp.now().normalize()
    df['Tvida'] = (today_dt - df['MinFechaEntrada_dt']).dt.days.fillna(0).astype(int)
    
    # Weekly sales trend list for Sparklines
    df['Tendencia'] = df.apply(lambda r: [r['VentasSemana4'], r['VentasSemana3'], r['VentasSemana2'], r['VentasSemana1']], axis=1)

    # Classification logic
    def classify(row):
        vel = row['Velocidad Venta (% entradas/dia)']
        acel = row['Aceleración (cambio de velocidad)']
        inv = row['InventarioActual']
        ent = row['Entradas']
        
        inv_pct = (inv / ent * 100.0) if ent > 0 else 0.0
        
        if inv_pct > inv_t and vel <= vel_t:
            return 'Riesgo de obsolescencia'
        elif vel > vel_t and acel > 0:
            return 'Ganadora'
        elif vel > vel_t and acel <= 0:
            return 'Buena perdiendo impulso'
        elif vel <= vel_t and acel > 0:
            return 'Emergente'
        else:
            return 'Crítica'

    df['Clasificación'] = df.apply(classify, axis=1)

    # 1. Insights Clave
    total_refs = len(df)
    ganadoras = df[df['Clasificación'] == 'Ganadora']
    pct_ganadoras = (len(ganadoras) / total_refs * 100) if total_refs else 0
    total_ventas = df['VentasAcumuladas'].sum()
    ventas_ganadoras = ganadoras['VentasAcumuladas'].sum()
    pct_ventas_ganadoras = (ventas_ganadoras / total_ventas * 100) if total_ventas else 0

    obsoletas = df[df['Clasificación'] == 'Riesgo de obsolescencia']
    pct_obsoletas = (len(obsoletas) / total_refs * 100) if total_refs else 0

    avg_vel = df['Velocidad Venta (% entradas/dia)'].mean()
    avg_acel = df['Aceleración (cambio de velocidad)'].mean()

    st.markdown(
        f"""
        <div style="background-color:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:18px; margin-bottom:20px; box-shadow: 0 4px 12px rgba(15, 23, 42, .04)">
            <h4 style="margin-top:0; margin-bottom:12px; color:#1e293b; display:flex; align-items:center; gap:8px; font-weight:700">💡 INSIGHTS CLAVE</h4>
            <ul style="margin-bottom:0; font-size:13.5px; color:#475569; padding-left:20px; line-height:1.6">
                <li><strong>{pct_ganadoras:.1f}%</strong> de las referencias son <strong>Ganadoras</strong> y representan el <strong>{pct_ventas_ganadoras:.1f}%</strong> de las ventas totales de este lote.</li>
                <li><strong>{pct_obsoletas:.1f}%</strong> de las referencias están en <strong>Riesgo de obsolescencia</strong>: se sugiere revisar estrategias de promoción o redistribución de stock.</li>
                <li>La velocidad promedio de venta es de <strong>{avg_vel:.2f}% de entradas/día</strong> (cambio promedio de <strong>{avg_acel:+.2f}% de entradas/día</strong> vs la semana anterior).</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 2. Donut Chart and Legend
    col1, col2 = st.columns([3, 2])
    
    with col1:
        class_counts = df['Clasificación'].value_counts().reset_index()
        class_counts.columns = ['Clasificación', 'Cantidad']
        
        color_map = {
            'Ganadora': '#2e7d32',
            'Buena perdiendo impulso': '#8bc34a',
            'Emergente': '#fbc02d',
            'Crítica': '#fb8c00',
            'Riesgo de obsolescencia': '#d32f2f'
        }
        
        fig = px.pie(
            class_counts,
            values='Cantidad',
            names='Clasificación',
            color='Clasificación',
            color_discrete_map=color_map,
            hole=0.5
        )
        fig.update_traces(textinfo='value+percent', textposition='inside', textfont=dict(size=12, color='white', weight='bold'))
        fig.update_layout(
            showlegend=False,
            margin=dict(t=10, b=10, l=10, r=10),
            height=300,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig, use_container_width=True, key="donut_clasificacion")

    with col2:
        st.markdown(
            """
            <div style="padding:10px 15px; border-left:4px solid #b91c1c; background-color:#f8fafc; border-radius:0 8px 8px 0; margin-top:20px">
                <h5 style="margin-top:0; font-weight:700; color:#0f172a; margin-bottom:12px">Clasificación Comercial (T-EXI-03)</h5>
                <div style="font-size:12px; line-height:1.7; color:#334155">
                    <span style="display:inline-block; width:12px; height:12px; background-color:#2e7d32; border-radius:50%; margin-right:6px"></span>
                    <strong>Ganadora:</strong> Velocidad alta y aceleración positiva.<br>
                    <span style="display:inline-block; width:12px; height:12px; background-color:#8bc34a; border-radius:50%; margin-right:6px"></span>
                    <strong>Buena perdiendo impulso:</strong> Velocidad alta y aceleración negativa.<br>
                    <span style="display:inline-block; width:12px; height:12px; background-color:#fbc02d; border-radius:50%; margin-right:6px"></span>
                    <strong>Emergente:</strong> Velocidad baja y aceleración positiva.<br>
                    <span style="display:inline-block; width:12px; height:12px; background-color:#fb8c00; border-radius:50%; margin-right:6px"></span>
                    <strong>Crítica:</strong> Velocidad baja y aceleración negativa.<br>
                    <span style="display:inline-block; width:12px; height:12px; background-color:#d32f2f; border-radius:50%; margin-right:6px"></span>
                    <strong>Riesgo de obsolescencia:</strong> Inventario alto (% entradas) y velocidad baja.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # 3. Detailed Dataframe
    st.markdown("<div style='height: 15px'></div>", unsafe_allow_html=True)
    section_title("Detalle por Referencia")
    
    # Calculate totals values
    tot_entradas = int(df['Entradas'].sum())
    tot_ventas = int(df['VentasAcumuladas'].sum())
    tot_inventario = int(df['InventarioActual'].sum())
    
    tot_ventas_1_3 = int(df['Ventas_1_3'].sum())
    tot_ventas_4_7 = int(df['Ventas_4_7'].sum())
    tot_ventas_8_12 = int(df['Ventas_8_12'].sum())
    
    tot_rot_1_3 = (tot_ventas_1_3 / tot_entradas * 100.0) if tot_entradas > 0 else 0.0
    tot_rot_4_7 = (tot_ventas_4_7 / tot_entradas * 100.0) if tot_entradas > 0 else 0.0
    tot_rot_8_12 = (tot_ventas_8_12 / tot_entradas * 100.0) if tot_entradas > 0 else 0.0
    
    tot_sell_through = (tot_ventas / tot_entradas * 100.0) if tot_entradas > 0 else 0.0
    
    tot_sem1 = df['VentasSemana1'].sum()
    tot_sem2 = df['VentasSemana2'].sum()
    tot_sem3 = df['VentasSemana3'].sum()
    tot_sem4 = df['VentasSemana4'].sum()
    
    tot_vel_actual = ((tot_sem1 / 7.0) / tot_entradas * 100.0) if tot_entradas > 0 else 0.0
    tot_vel_prev = ((tot_sem2 / 7.0) / tot_entradas * 100.0) if tot_entradas > 0 else 0.0
    tot_acel = tot_vel_actual - tot_vel_prev
    
    tot_cobertura = (tot_inventario / (tot_sem1 / 7.0)) if tot_sem1 > 0 else 999.0
    tot_rotacion = (tot_ventas / ((tot_entradas + tot_inventario) / 2.0) * 100.0) if (tot_entradas + tot_inventario) > 0 else 0.0
    
    avg_tvida = int(round(df['Tvida'].mean())) if not df['Tvida'].empty else 0
    tot_tendencia = [int(tot_sem4), int(tot_sem3), int(tot_sem2), int(tot_sem1)]
    
    totals_row = pd.DataFrame([{
        'Referencia': 'TOTALES',
        'Descripcion': 'Resumen General',
        'Embarque': '',
        'Entradas': tot_entradas,
        'Tvida': avg_tvida,
        'VentasAcumuladas': tot_ventas,
        'InventarioActual': tot_inventario,
        'Rotación: 1-3': round(tot_rot_1_3, 2),
        'Rotación: 4-7': round(tot_rot_4_7, 2),
        'Rotación: 8-12': round(tot_rot_8_12, 2),
        'Sell Through Acumulado (%)': round(tot_sell_through, 2),
        'Velocidad Venta (% entradas/dia)': round(tot_vel_actual, 2),
        'Aceleración (cambio de velocidad)': round(tot_acel, 2),
        'Cobertura (dias)': int(round(tot_cobertura)),
        'Rotación (ventas / inv. promedio)': round(tot_rotacion, 2),
        'Clasificación': '',
        'Tendencia': tot_tendencia
    }])

    display_df = df[[
        'Referencia', 'Descripcion', 'Embarque', 'Entradas', 'Tvida', 'VentasAcumuladas', 'InventarioActual',
        'Rotación: 1-3', 'Rotación: 4-7', 'Rotación: 8-12',
        'Sell Through Acumulado (%)', 'Velocidad Venta (% entradas/dia)', 'Aceleración (cambio de velocidad)',
        'Cobertura (dias)', 'Rotación (ventas / inv. promedio)', 'Clasificación', 'Tendencia'
    ]].copy()
    
    # Round float columns to 2 decimal places, cobertura to 0 decimals, and percentages * 100
    display_df['Rotación: 1-3'] = (display_df['Rotación: 1-3'] * 100.0).round(2)
    display_df['Rotación: 4-7'] = (display_df['Rotación: 4-7'] * 100.0).round(2)
    display_df['Rotación: 8-12'] = (display_df['Rotación: 8-12'] * 100.0).round(2)
    display_df['Sell Through Acumulado (%)'] = (display_df['Sell Through Acumulado (%)'] * 100.0).round(2)
    display_df['Velocidad Venta (% entradas/dia)'] = display_df['Velocidad Venta (% entradas/dia)'].round(2)
    display_df['Aceleración (cambio de velocidad)'] = display_df['Aceleración (cambio de velocidad)'].round(2)
    display_df['Cobertura (dias)'] = display_df['Cobertura (dias)'].round(0).fillna(999).astype(int)
    display_df['Rotación (ventas / inv. promedio)'] = (display_df['Rotación (ventas / inv. promedio)'] * 100.0).round(2)
    
    # Concatenate display_df with totals_row
    display_df = pd.concat([display_df, totals_row], ignore_index=True)
    
    display_df = display_df.rename(columns={
        'Referencia': 'Referencia',
        'Descripcion': 'Descripción',
        'Embarque': 'Embarque',
        'Entradas': 'Entradas<br>Lote',
        'Tvida': 'Días<br>Vida',
        'VentasAcumuladas': 'Ventas<br>Acum.',
        'InventarioActual': 'Stock<br>Actual',
        'Rotación: 1-3': 'Rotación<br>1-3',
        'Rotación: 4-7': 'Rotación<br>4-7',
        'Rotación: 8-12': 'Rotación<br>8-12',
        'Sell Through Acumulado (%)': 'Rotación<br>Acum.',
        'Velocidad Venta (% entradas/dia)': 'Velocidad<br>(1ra Deriv)',
        'Aceleración (cambio de velocidad)': 'Aceleración<br>(2da Deriv)',
        'Cobertura (dias)': 'Cobertura<br>(días)',
        'Rotación (ventas / inv. promedio)': 'Índice<br>Rotación',
        'Clasificación': 'Clasificación<br>Comercial',
        'Tendencia': 'Tendencia<br>(4 Sem)'
    })

    # Apply sparkline converter to lists in Tendencia
    display_df['Tendencia<br>(4 Sem)'] = display_df['Tendencia<br>(4 Sem)'].apply(
        lambda x: _make_sparkline_svg(x) if isinstance(x, list) else x
    )

    # Styling helper for colored classification blocks
    def style_clasificacion(val):
        colors = {
            'Ganadora': 'background-color: #d4edda; color: #155724; font-weight: bold;',
            'Buena perdiendo impulso': 'background-color: #e2f0d9; color: #2e7d32;',
            'Emergente': 'background-color: #fff3cd; color: #856404;',
            'Crítica': 'background-color: #ffe0b2; color: #e65100;',
            'Riesgo de obsolescencia': 'background-color: #f8d7da; color: #721c24; font-weight: bold;'
        }
        return colors.get(val, '')

    def style_row(row):
        if row['Referencia'] == 'TOTALES':
            return ['background-color: #f1f5f9; font-weight: bold; color: #0f172a; border-top: 2px solid #cbd5e1;'] * len(row)
        return [''] * len(row)

    styled_df = display_df.style.applymap(style_clasificacion, subset=['Clasificación<br>Comercial'])\
                               .apply(style_row, axis=1)\
                               .format({
                                   'Rotación<br>1-3': '{:.2f}%',
                                   'Rotación<br>4-7': '{:.2f}%',
                                   'Rotación<br>8-12': '{:.2f}%',
                                   'Rotación<br>Acum.': '{:.2f}%',
                                   'Velocidad<br>(1ra Deriv)': '{:.2f}%',
                                   'Aceleración<br>(2da Deriv)': '{:+.2f}%',
                                   'Índice<br>Rotación': '{:.2f}%',
                                   'Cobertura<br>(días)': '{:d}'
                                })

    table_css = """
    <style>
    .custom-report-table {
        width: 100%;
        border-collapse: collapse;
        font-family: inherit;
        font-size: 13px;
        color: #1e293b;
    }
    .custom-report-table th {
        background-color: #f8fafc;
        color: #000000 !important;
        font-weight: 800 !important;
        text-align: center;
        padding: 10px 8px;
        border: 1px solid #cbd5e1;
        font-size: 12.5px;
        line-height: 1.3;
    }
    .custom-report-table td {
        padding: 8px 10px;
        border: 1px solid #e2e8f0;
        text-align: center;
        vertical-align: middle;
    }
    .custom-report-table tr:hover {
        background-color: #f8fafc;
    }
    </style>
    """

    st.markdown(table_css, unsafe_allow_html=True)
    table_html = styled_df.to_html(
        classes="custom-report-table",
        escape=False,
        index=False
    )
    st.markdown(
        f'<div style="overflow-x: auto; border: 1px solid #cbd5e1; border-radius: 12px; box-shadow: 0 4px 16px rgba(16, 24, 40, .045); background: #ffffff;">{table_html}</div>',
        unsafe_allow_html=True
    )

    # Formula reference panel
    st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
            <div style="font-size: 14px; font-weight: bold; color: #1e293b; margin-bottom: 10px; border-bottom: 1px solid #e2e8f0; padding-bottom: 5px;">
                💡 Guía de Fórmulas y Definiciones del Reporte (T-EXI-03)
            </div>
            <table style="width: 100%; border-collapse: collapse; font-size: 13px; color: #334155;">
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 8px 0; font-weight: 650; width: 30%;">Rotación: 1-3</td>
                    <td style="padding: 8px 0; font-size: 15px; color: #800020;"><span style="font-family: monospace; font-size: 15px; color: #800020; background-color: #fff5f5; border: 1px solid #fee2e2; padding: 2px 6px; border-radius: 4px; font-weight: 500;">(Ventas Día 0 a Fin Día 3 / Entradas) * 100</span> &nbsp; <span style="color:#9f1239; font-size: 14px; font-style: italic;">(desde la fecha de entrada de la referencia)</span></td>
                </tr>
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 8px 0; font-weight: 650;">Rotación: 4-7</td>
                    <td style="padding: 8px 0; font-size: 15px; color: #800020;"><span style="font-family: monospace; font-size: 15px; color: #800020; background-color: #fff5f5; border: 1px solid #fee2e2; padding: 2px 6px; border-radius: 4px; font-weight: 500;">(Ventas Inicio Día 4 a Fin Día 7 / Entradas) * 100</span> &nbsp; <span style="color:#9f1239; font-size: 14px; font-style: italic;">(desde la fecha de entrada de la referencia)</span></td>
                </tr>
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 8px 0; font-weight: 650;">Rotación: 8-12</td>
                    <td style="padding: 8px 0; font-size: 15px; color: #800020;"><span style="font-family: monospace; font-size: 15px; color: #800020; background-color: #fff5f5; border: 1px solid #fee2e2; padding: 2px 6px; border-radius: 4px; font-weight: 500;">(Ventas Inicio Día 8 a Fin Día 12 / Entradas) * 100</span> &nbsp; <span style="color:#9f1239; font-size: 14px; font-style: italic;">(desde la fecha de entrada de la referencia)</span></td>
                </tr>
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 8px 0; font-weight: 650;">Rotación Acum.</td>
                    <td style="padding: 8px 0; font-size: 15px; color: #800020;"><span style="font-family: monospace; font-size: 15px; color: #800020; background-color: #fff5f5; border: 1px solid #fee2e2; padding: 2px 6px; border-radius: 4px; font-weight: 500;">(Ventas Acumuladas / Entradas) * 100</span></td>
                </tr>
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 8px 0; font-weight: 650;">Velocidad de Venta (1ra Derivada)</td>
                    <td style="padding: 8px 0; font-size: 15px; color: #800020;"><span style="font-family: monospace; font-size: 15px; color: #800020; background-color: #fff5f5; border: 1px solid #fee2e2; padding: 2px 6px; border-radius: 4px; font-weight: 500;">((Ventas Últimos 7 Días / 7) / Entradas) * 100</span> &nbsp; <span style="color:#9f1239; font-size: 14px; font-style: italic;">(% de salida diaria del lote)</span></td>
                </tr>
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 8px 0; font-weight: 650;">Aceleración (2da Derivada)</td>
                    <td style="padding: 8px 0; font-size: 15px; color: #800020;"><span style="font-family: monospace; font-size: 15px; color: #800020; background-color: #fff5f5; border: 1px solid #fee2e2; padding: 2px 6px; border-radius: 4px; font-weight: 500;">Velocidad de Venta Actual - Velocidad de Venta de Semana Anterior</span></td>
                </tr>
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 8px 0; font-weight: 650;">Cobertura (días)</td>
                    <td style="padding: 8px 0; font-size: 15px; color: #800020;"><span style="font-family: monospace; font-size: 15px; color: #800020; background-color: #fff5f5; border: 1px solid #fee2e2; padding: 2px 6px; border-radius: 4px; font-weight: 500;">Inventario Actual / (Ventas Últimos 7 Días / 7)</span></td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: 650;">Índice de Rotación</td>
                    <td style="padding: 8px 0; font-size: 15px; color: #800020;"><span style="font-family: monospace; font-size: 15px; color: #800020; background-color: #fff5f5; border: 1px solid #fee2e2; padding: 2px 6px; border-radius: 4px; font-weight: 500;">(Ventas Acumuladas / Inventario Promedio) * 100</span> &nbsp; <span style="color:#9f1239; font-size: 14px; font-style: italic;">donde Inventario Promedio = (Entradas + Inventario Actual) / 2</span></td>
                </tr>
            </table>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Report code moved after shipment filter

    # Excel export
    export_df = df[[
        'Referencia', 'Descripcion', 'Embarque', 'Entradas', 'Tvida', 'VentasAcumuladas', 'InventarioActual',
        'Rotación: 1-3', 'Rotación: 4-7', 'Rotación: 8-12',
        'Sell Through Acumulado (%)', 'Velocidad Venta (% entradas/dia)', 'Aceleración (cambio de velocidad)',
        'Cobertura (dias)', 'Rotación (ventas / inv. promedio)', 'Clasificación'
    ]].copy()
    export_df['Rotación: 1-3'] = export_df['Rotación: 1-3'] * 100.0
    export_df['Rotación: 4-7'] = export_df['Rotación: 4-7'] * 100.0
    export_df['Rotación: 8-12'] = export_df['Rotación: 8-12'] * 100.0
    export_df['Sell Through Acumulado (%)'] = export_df['Sell Through Acumulado (%)'] * 100.0
    export_df['Rotación (ventas / inv. promedio)'] = export_df['Rotación (ventas / inv. promedio)'] * 100.0
    export_df = export_df.rename(columns={
        'Sell Through Acumulado (%)': 'Rotación Acum. (%)',
        'Rotación (ventas / inv. promedio)': 'Rotación (%)'
    })

    # Add totals row to export_df as well
    export_totals = pd.DataFrame([{
        'Referencia': 'TOTALES',
        'Descripcion': 'Resumen General',
        'Embarque': '',
        'Entradas': tot_entradas,
        'Tvida': avg_tvida,
        'VentasAcumuladas': tot_ventas,
        'InventarioActual': tot_inventario,
        'Rotación: 1-3': round(tot_rot_1_3, 2),
        'Rotación: 4-7': round(tot_rot_4_7, 2),
        'Rotación: 8-12': round(tot_rot_8_12, 2),
        'Rotación Acum. (%)': round(tot_sell_through, 2),
        'Velocidad Venta (% entradas/dia)': round(tot_vel_actual, 2),
        'Aceleración (cambio de velocidad)': round(tot_acel, 2),
        'Cobertura (dias)': int(round(tot_cobertura)),
        'Rotación (%)': round(tot_rotacion, 2),
        'Clasificación': ''
    }])
    export_df = pd.concat([export_df, export_totals], ignore_index=True)

    st.download_button(
        "Exportar Rotación Derivada a Excel",
        dataframe_to_excel_bytes({"Rotación Derivada": export_df}),
        file_name=export_filename("wally_rotacion_derivada", "xlsx"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key="btn_export_rotacion"
    )
