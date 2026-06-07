from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st

from services import db
from services.branches import filter_frame
from services.catalog import get_code
from services.exports import dataframe_to_excel_bytes, export_filename
from services.local_store import connect, get_param, read_table
from services.ui import code_footer, display_table, page_title, section_title, warning_box


CRM_ESTADOS = [
    "Pendiente",
    "Llamado",
    "No contesto",
    "Interesado",
    "Visitar tienda",
    "Enviar informacion",
    "Compro",
    "No interesado",
    "Reprogramado",
]


def _candidate_query(segmentos: list[str], limit: int) -> pd.DataFrame:
    where = "DiasSinCompra >= 1"
    if segmentos:
        where += f" AND SegmentoSinCompra IN ({db.sql_literal_list(segmentos)})"
    return db.read_sql(
        f"""
        SELECT TOP {int(limit)}
            NumeroCliente,
            NitDpi,
            Cliente,
            Telefono,
            Celular,
            Email,
            FechaUltimaCompra,
            DiasSinCompra,
            SegmentoSinCompra,
            SucursalPreferida,
            VendedorUltimaFactura,
            FacturasTotales,
            UnidadesTotales,
            VentaNetaTotal,
            UnidadesFullPrecio,
            UnidadesPromocion,
            PorcentajeFullPrecio,
            PorcentajePromocion
        FROM {db.VIEW_CRM}
        WHERE {where}
        ORDER BY
            DiasSinCompra DESC,
            VentaNetaTotal DESC,
            FacturasTotales DESC,
            CASE WHEN Celular IS NULL OR LTRIM(RTRIM(Celular)) = '' THEN 1 ELSE 0 END,
            Cliente ASC
        """
    )


def _create_suggestions(candidates: pd.DataFrame, quota: int) -> int:
    if candidates.empty:
        return 0
    today = date.today().isoformat()
    inserted = 0
    conn = connect()
    try:
        for _, row in candidates.head(quota * max(1, candidates["VendedorUltimaFactura"].nunique())).iterrows():
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO crm_asignaciones
                (fecha_asignacion, nit_dpi, cliente, sucursal_preferida, vendedor_responsable, estado, aprobado, creado_en)
                VALUES (?, ?, ?, ?, ?, 'Pendiente', 0, ?)
                """,
                (
                    today,
                    str(row["NitDpi"]),
                    str(row["Cliente"]),
                    str(row.get("SucursalPreferida", "")),
                    str(row.get("VendedorUltimaFactura", "")),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            inserted += cursor.rowcount
        conn.commit()
        return inserted
    finally:
        conn.close()


def _approve_today() -> int:
    conn = connect()
    try:
        cursor = conn.execute(
            "UPDATE crm_asignaciones SET aprobado = 1 WHERE fecha_asignacion = ? AND aprobado = 0",
            (date.today().isoformat(),),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def _register_management(nit_dpi: str, resultado: str, observacion: str, proxima_llamada, vendedor: str) -> None:
    conn = connect()
    try:
        assignment = conn.execute(
            """
            SELECT id FROM crm_asignaciones
            WHERE fecha_asignacion = ? AND nit_dpi = ?
            ORDER BY id DESC LIMIT 1
            """,
            (date.today().isoformat(), nit_dpi),
        ).fetchone()
        assignment_id = assignment["id"] if assignment else None
        conn.execute(
            """
            INSERT INTO crm_gestiones
            (asignacion_id, nit_dpi, resultado, observacion, proxima_llamada, vendedor_responsable, usuario, creado_en)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assignment_id,
                nit_dpi,
                resultado,
                observacion,
                proxima_llamada.isoformat() if proxima_llamada else None,
                vendedor,
                "local",
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        if assignment_id:
            conn.execute("UPDATE crm_asignaciones SET estado = ? WHERE id = ?", (resultado, assignment_id))
        conn.commit()
    finally:
        conn.close()


def render() -> None:
    page_title("CRM", "Clientes sin compra, sugerencias de llamada, aprobacion y gestion")
    code_footer(*get_code("crm", "report"))
    quota = int(get_param("crm_cuota_diaria_vendedor", "60") or 60)
    st.sidebar.markdown("### CRM")
    st.sidebar.caption(f"Cuota diaria configurada: {quota} llamadas por vendedor")
    segmentos = st.sidebar.multiselect(
        "Segmento sin compra",
        ["1 a 60 dias", "61 a 120 dias", "121 dias en adelante"],
        default=["1 a 60 dias", "61 a 120 dias", "121 dias en adelante"],
    )

    try:
        candidates = _candidate_query(segmentos, max(100, quota * 20))
    except Exception as exc:
        st.error("No se pudo consultar VwClienteResumenCRM.")
        st.exception(exc)
        return

    cols = st.columns(3)
    with cols[0]:
        if st.button("Generar sugerencias de hoy", type="primary"):
            inserted = _create_suggestions(candidates, quota)
            st.success(f"Sugerencias creadas: {inserted}")
    with cols[1]:
        if st.button("Aprobar sugerencias de hoy"):
            approved = _approve_today()
            st.success(f"Asignaciones aprobadas: {approved}")
    with cols[2]:
        st.download_button(
            "Exportar candidatos",
            dataframe_to_excel_bytes({"CRM_Candidatos": candidates}),
            file_name=export_filename("wally_crm_candidatos"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    section_title("Clientes sugeridos por Wally")
    if candidates.empty:
        warning_box("No hay clientes candidatos para los segmentos seleccionados.")
    else:
        display_table(candidates, height=430)
    code_footer(*get_code("crm", "candidates_table"))

    section_title("Asignaciones locales")
    assignments = filter_frame(read_table("crm_asignaciones"), ["sucursal_preferida"])
    display_table(assignments.sort_values("id", ascending=False).head(300), height=330, show_total=False)
    code_footer(*get_code("crm", "assignments_table"))

    section_title("Registrar gestion")
    if not assignments.empty:
        approved = assignments[assignments["aprobado"] == 1].copy()
        if approved.empty:
            st.info("Primero apruebe las sugerencias del dia para registrar gestion.")
        else:
            selected = st.selectbox(
                "Cliente",
                approved.sort_values("cliente")["nit_dpi"].tolist(),
                format_func=lambda nit: f"{nit} - {approved.loc[approved['nit_dpi'] == nit, 'cliente'].iloc[0]}",
            )
            row = approved.loc[approved["nit_dpi"] == selected].iloc[0]
            resultado = st.selectbox("Resultado", CRM_ESTADOS, index=0)
            proxima = st.date_input("Fecha proxima llamada", value=None)
            observacion = st.text_area("Observacion opcional")
            if st.button("Guardar gestion"):
                _register_management(selected, resultado, observacion, proxima, str(row["vendedor_responsable"]))
                st.success("Gestion registrada.")
    code_footer(*get_code("crm", "management_form"))

    section_title("Historial de gestiones")
    display_table(read_table("crm_gestiones").sort_values("id", ascending=False).head(300), height=330, show_total=False)
    code_footer(*get_code("crm", "history_table"))
