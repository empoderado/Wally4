from __future__ import annotations

import streamlit as st

from memory.store import memory_snapshot, remember
from memory.store import recent_conversations
from orchestration.maria_orchestrator import answer
from services.local_store import DEFAULT_AGENT_PROMPT, get_param, set_param
from services.ui import page_title, section_title


def render() -> None:
    page_title("Mar-IA Agent", "Copiloto ejecutivo con memoria, SQL seguro y entrenamiento")

    if "maria_messages" not in st.session_state:
        st.session_state.maria_messages = [
            {
                "role": "assistant",
                "content": "Hola, soy Mar-IA Agent. Puedo consultar ventas e inventario autorizado de Wally.",
            }
        ]

    for message in st.session_state.maria_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input("Preguntale a Mar-IA Agent")
    if question:
        st.session_state.maria_messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        response = answer(question, channel="app", user_id="local", user_name="Usuario local")
        st.session_state.maria_messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)

    with st.expander("Configuracion del prompt base"):
        prompt = st.text_area(
            "Personalidad y reglas",
            value=get_param("maria_agent_prompt", DEFAULT_AGENT_PROMPT),
            height=260,
        )
        if st.button("Guardar prompt"):
            set_param("maria_agent_prompt", prompt.strip() or DEFAULT_AGENT_PROMPT, "Prompt base editable de Mar-IA Agent")
            st.success("Prompt guardado.")

    with st.expander("Memoria reciente"):
        df = recent_conversations(limit=20)
        if df.empty:
            st.caption("Aun no hay conversaciones registradas.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)

    with st.expander("Memoria formal de Mar-IA"):
        snapshot = memory_snapshot(user_id="local")
        tab_short, tab_medium, tab_permanent, tab_add = st.tabs(["Corto plazo", "Mediano plazo", "Permanente", "Agregar"])
        with tab_short:
            st.caption("Conversaciones recientes usadas para contexto inmediato.")
            if snapshot.short_term.empty:
                st.caption("Sin memoria de corto plazo.")
            else:
                st.dataframe(snapshot.short_term, use_container_width=True, hide_index=True)
        with tab_medium:
            st.caption("Recuerdos temporales con vencimiento.")
            if snapshot.medium_term.empty:
                st.caption("Sin memoria de mediano plazo.")
            else:
                st.dataframe(snapshot.medium_term, use_container_width=True, hide_index=True)
        with tab_permanent:
            st.caption("Recuerdos aprobados sin vencimiento.")
            if snapshot.permanent.empty:
                st.caption("Sin memoria permanente.")
            else:
                st.dataframe(snapshot.permanent, use_container_width=True, hide_index=True)
        with tab_add:
            with st.form("manual_memory_form", clear_on_submit=True):
                memory_type = st.selectbox("Tipo de memoria", ["medium", "permanent"], format_func=lambda value: "Mediano plazo" if value == "medium" else "Permanente")
                key_text = st.text_input("Clave", placeholder="preferred_branch")
                value_text = st.text_area("Valor", placeholder="OAKLAND")
                days = st.number_input("Dias de vigencia", min_value=1, max_value=3650, value=90, disabled=memory_type == "permanent")
                submitted = st.form_submit_button("Guardar memoria")
                if submitted:
                    if not key_text.strip() or not value_text.strip():
                        st.warning("Debe indicar clave y valor.")
                    else:
                        remember(
                            memory_type=memory_type,
                            key_text=key_text,
                            value_text=value_text,
                            user_id="local",
                            days=int(days),
                        )
                        st.success("Memoria guardada.")

    section_title("Estado")
    st.info("Memoria activa: corto plazo por conversaciones, mediano plazo con vencimiento y permanente aprobada en SQLite.")
