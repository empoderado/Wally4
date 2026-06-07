from __future__ import annotations

from html import escape

import streamlit as st

from memory.conversation_context import clear_result_context, load_result_context
from orchestration.maria_orchestrator import answer
from services.maria_ai import configuration_status
from services.ui import page_title


USER_ID = "local"
WELCOME_MESSAGE = (
    "Hola, soy **Mar-IA**. Puedo consultar datos autorizados de Wally, "
    "recordar el contexto y ayudarte con analisis y planes de accion."
)
def render() -> None:
    _inject_chat_styles()
    page_title("Mar-IA", "Copiloto ejecutivo para consultar, analizar y tomar accion")
    _ensure_session()

    _render_status_header()
    _render_messages()

    with st.container():
        question = st.chat_input("Escribe una pregunta para Mar-IA")
    if question:
        _run_question(question)
        st.rerun()


def _ensure_session() -> None:
    if "maria_messages" not in st.session_state:
        st.session_state.maria_messages = [{"role": "assistant", "content": WELCOME_MESSAGE}]


def _render_status_header() -> None:
    ai_status = configuration_status()
    context = load_result_context(USER_ID)
    status_label = (
        f"{ai_status['provider'].upper()} · {ai_status['model']}"
        if ai_status["configured"]
        else "Motor local"
    )
    context_parts = []
    if context:
        if context.focus_entity:
            context_parts.append(f"{context.focus_label or 'Enfoque'}: {context.focus_entity}")
        elif context.branch:
            context_parts.append(f"Sucursal: {context.branch}")
        if context.date_start and context.date_end:
            period = context.date_label or f"{context.date_start} a {context.date_end}"
            context_parts.append(f"Periodo: {period}")
        context_parts.append(f"Consulta: {context.title}")
    context_label = " · ".join(context_parts) if context_parts else "Sin contexto activo"

    left, right = st.columns([0.78, 0.22], vertical_alignment="center")
    with left:
        st.markdown(
            f"""
            <div class="maria-status-card">
                <div><span class="maria-status-dot"></span><strong>IA activa:</strong> {escape(status_label)}</div>
                <div class="maria-context-line"><strong>Contexto:</strong> {escape(context_label)}</div>
                <div class="maria-source-line">Datos de WallyBD · consultas de solo lectura</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        if st.button("Nueva conversacion", key="maria_new_conversation", use_container_width=True):
            st.session_state.maria_messages = [{"role": "assistant", "content": WELCOME_MESSAGE}]
            clear_result_context(USER_ID)
            st.rerun()


def _render_messages() -> None:
    st.markdown('<div class="maria-chat-label">Conversacion</div>', unsafe_allow_html=True)
    with st.container(border=True):
        for message in st.session_state.maria_messages:
            avatar = "👤" if message["role"] == "user" else "✨"
            with st.chat_message(message["role"], avatar=avatar):
                st.markdown(message["content"])


def _run_question(question: str) -> None:
    clean_question = question.strip()
    if not clean_question:
        return
    st.session_state.maria_messages.append({"role": "user", "content": clean_question})
    with st.chat_message("user", avatar="👤"):
        st.markdown(clean_question)
    with st.chat_message("assistant", avatar="✨"):
        with st.spinner("Mar-IA consulta y analiza la informacion..."):
            response = answer(
                clean_question,
                channel="app",
                user_id=USER_ID,
                user_name="Usuario local",
            )
        st.markdown(response)
    st.session_state.maria_messages.append({"role": "assistant", "content": response})


def _inject_chat_styles() -> None:
    st.markdown(
        """
        <style>
        .maria-status-card {
            border: 1px solid #e5e7eb;
            border-left: 4px solid #ef4444;
            border-radius: 12px;
            padding: 12px 16px;
            background: linear-gradient(135deg, #ffffff 0%, #fff7ed 100%);
            margin-bottom: 6px;
        }
        .maria-status-dot {
            display: inline-block;
            width: 9px;
            height: 9px;
            margin-right: 7px;
            border-radius: 50%;
            background: #22c55e;
            box-shadow: 0 0 0 3px rgba(34,197,94,.14);
        }
        .maria-context-line { margin-top: 5px; color: #374151; }
        .maria-source-line { margin-top: 3px; color: #6b7280; font-size: .82rem; }
        .maria-chat-label {
            margin: 14px 0 7px;
            color: #374151;
            font-size: .83rem;
            font-weight: 800;
            letter-spacing: .02em;
            text-transform: uppercase;
        }
        div[data-testid="stChatMessage"] {
            border-radius: 12px;
            padding: 4px 8px;
        }
        div[data-testid="stChatInput"] {
            border-top: 1px solid #e5e7eb;
            padding-top: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
