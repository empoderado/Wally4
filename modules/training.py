from __future__ import annotations

import streamlit as st

from services.local_store import add_training_entry, read_table, upsert_semantic_term
from services.ui import page_title, section_title


def render() -> None:
    page_title("Entrenamiento", "Diccionario de negocio y aprendizaje semisupervisado")

    tab_dictionary, tab_examples = st.tabs(["Diccionario semantico", "Ejemplos aprobados"])

    with tab_dictionary:
        section_title("Nuevo termino")
        with st.form("semantic_dictionary_form", clear_on_submit=True):
            term = st.text_input("Termino de negocio", placeholder="Ejemplo: stock")
            definition = st.text_area("Definicion", placeholder="Ejemplo: existencia fisica y disponible de inventario")
            aliases = st.text_input("Alias separados por coma", placeholder="Ejemplo: inventario, existencia, unidades disponibles")
            approved = st.checkbox("Aprobado para Mar-IA", value=True)
            submitted = st.form_submit_button("Guardar termino")
            if submitted:
                if not term.strip() or not definition.strip():
                    st.warning("Debe ingresar termino y definicion.")
                else:
                    upsert_semantic_term(term, definition, aliases, approved)
                    st.success("Termino guardado.")

        section_title("Diccionario actual")
        st.dataframe(read_table("semantic_dictionary"), use_container_width=True, hide_index=True)

    with tab_examples:
        section_title("Nuevo ejemplo")
        intents = [
            "sales_summary",
            "sales_by_branch",
            "sales_by_seller",
            "sales_by_shipment",
            "sales_by_line",
            "sales_year_comparison",
            "inventory_by_branch",
            "inventory_by_shipment",
            "inventory_reference",
            "help",
        ]
        with st.form("training_examples_form", clear_on_submit=True):
            question = st.text_area("Pregunta de ejemplo", placeholder="Ejemplo: como va oakland hoy")
            expected_intent = st.selectbox("Intencion esperada", intents)
            expected_response = st.text_area("Respuesta esperada opcional")
            approved = st.checkbox("Aprobado para Mar-IA", value=True, key="training_approved")
            submitted = st.form_submit_button("Guardar ejemplo")
            if submitted:
                if not question.strip():
                    st.warning("Debe ingresar una pregunta de ejemplo.")
                else:
                    add_training_entry(question, expected_intent, expected_response, approved)
                    st.success("Ejemplo guardado.")

        section_title("Ejemplos actuales")
        st.dataframe(read_table("training_entries"), use_container_width=True, hide_index=True)
