from __future__ import annotations

import streamlit as st

from services.catalog import get_code
from services.exports import dataframe_to_excel_bytes, export_filename
from services.transfers import (
    generate_fifo_xl,
    load_branch_priorities,
    load_inventory,
    load_reference_rotation,
    official_branches,
    official_lines,
    official_sublines,
)
from services.ui import code_footer, display_table, metric_card, page_title, section_title, warning_box


def render() -> None:
    page_title("Traslados", "Cruce de mercancia e inventario entre sucursales")
    code_footer(*get_code("traslados", "report"))

    try:
        branches = official_branches()
        priorities = load_branch_priorities(branches)
    except Exception as exc:
        st.error("No se pudieron cargar tiendas o prioridades.")
        st.exception(exc)
        return

    active = priorities[priorities["Prioridad"].astype(int) > 0].copy()
    if active.empty:
        st.info("Configure prioridades de tienda en Configuracion > Traslados. Las tiendas con prioridad 0 no participan.")
        return

    active_branches = active.sort_values(["Prioridad", "Sucursal"])["Sucursal"].tolist()

    top_cols = st.columns([1, 1.2, 2.2])
    with top_cols[0]:
        max_units = int(st.number_input("Maximo de unidades a trasladar", min_value=1, max_value=100000, value=1000, step=50))
    with top_cols[1]:
        destination_mode = st.radio(
            "Tiendas destino",
            ["Todas las tiendas activas", "Una tienda", "Varias tiendas"],
            horizontal=False,
        )
    with top_cols[2]:
        if destination_mode == "Todas las tiendas activas":
            destination_branches = active_branches
            st.caption("Destino: todas las tiendas con prioridad mayor a cero.")
        elif destination_mode == "Una tienda":
            selected = st.selectbox("Sucursal que recibe", active_branches)
            destination_branches = [selected]
        else:
            destination_branches = st.multiselect("Sucursales que reciben", active_branches, default=active_branches)

    try:
        all_lines = official_lines()
    except Exception as exc:
        st.error("No se pudieron cargar lineas activas.")
        st.exception(exc)
        return

    filter_cols = st.columns(2)
    with filter_cols[0]:
        selected_lines = st.multiselect(
            "Lineas activas para cruce",
            all_lines,
            default=all_lines,
            help="Quite las lineas que no deben participar en el procedimiento de cruce.",
        )

    try:
        all_sublines = official_sublines(selected_lines)
    except Exception as exc:
        st.error("No se pudieron cargar sublineas activas.")
        st.exception(exc)
        return

    with filter_cols[1]:
        selected_sublines = st.multiselect(
            "Sublineas activas para cruce",
            all_sublines,
            default=all_sublines,
            help="Quite las sublineas que no deben participar en el procedimiento de cruce.",
        )

    st.caption(
        "Orden aplicado: 1) embarque mas reciente por TVida menor, 2) destino por prioridad menor, "
        "3) origen por prioridad mayor. Prioridad 0 excluye la tienda."
    )

    if st.button("Generar FIFO-XLS", type="primary"):
        try:
            inventory = load_inventory()
            rotation_metrics = load_reference_rotation()
            if selected_lines:
                inventory = inventory[inventory["Linea"].isin(selected_lines)].copy()
            else:
                inventory = inventory.iloc[0:0].copy()
            if selected_sublines:
                inventory = inventory[inventory["Sublinea"].isin(selected_sublines)].copy()
            else:
                inventory = inventory.iloc[0:0].copy()
            result = generate_fifo_xl(
                inventory,
                priorities,
                max_units=max_units,
                destination_branches=destination_branches,
                rotation_metrics=rotation_metrics,
            )
        except Exception as exc:
            st.error("No se pudo generar FIFO-XLS.")
            st.exception(exc)
            return

        st.session_state["traslados_fifo_xls"] = result

    result = st.session_state.get("traslados_fifo_xls")
    if result is None:
        warning_box(
            "FIFO-XLS es una sugerencia operativa. No modifica el ERP ni genera documentos automaticamente. "
            "El usuario debe validar fisicamente el traslado antes de ejecutarlo."
        )
        return

    section_title("FIFO-XLS")
    code_footer(*get_code("traslados", "fifo_xl"))

    if result.empty:
        st.info("No se generaron sugerencias con la configuracion actual.")
        warning_box(
            "FIFO-XLS es una sugerencia operativa. No modifica el ERP ni genera documentos automaticamente. "
            "El usuario debe validar fisicamente el traslado antes de ejecutarlo."
        )
        return

    cols = st.columns(3)
    with cols[0]:
        metric_card("Sugerencias", f"{len(result):,.0f}".replace(",", "."))
    with cols[1]:
        metric_card("Unidades sugeridas", f"{int(result['CANTIDAD'].sum()):,.0f}".replace(",", "."))
    with cols[2]:
        metric_card("Destinos", f"{result['DESTINO TIENDA QUE RECIBE'].nunique():,.0f}".replace(",", "."))

    display_table(result, height=520, show_total=True)
    st.download_button(
        "Exportar FIFO-XLS a Excel",
        dataframe_to_excel_bytes({"FIFO-XLS": result}),
        file_name=export_filename("wally_fifo_xls"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    warning_box(
        "FIFO-XLS es una sugerencia operativa. No modifica el ERP ni genera documentos automaticamente. "
        "El usuario debe validar fisicamente el traslado antes de ejecutarlo."
    )
