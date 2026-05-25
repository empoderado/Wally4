from __future__ import annotations

import os

import streamlit as st

from modules import presupuesto
from services import db
from services.env import env_value
from services.local_store import DEFAULT_MARIA_PERSONALITY_PROMPT, get_param, read_table, set_param
from services.paths import APP_DIR, sqlite_path
from services.transfers import load_branch_priorities, official_branches, save_branch_priorities
from services.ui import display_table, page_title, section_title


PROVIDERS = ["openai", "gemini", "deepseek", "openai_compatible"]
TRANSCRIPTION_PROVIDERS = ["openai", "local"]
PROVIDER_LABELS = {
    "openai": "OpenAI",
    "gemini": "Gemini",
    "deepseek": "DeepSeek",
    "openai_compatible": "Otro compatible",
}
DEFAULT_MODELS = {
    "openai": "gpt-4.1-mini",
    "gemini": "gemini-1.5-flash",
    "deepseek": "deepseek-chat",
    "openai_compatible": "",
}
DEFAULT_URLS = {
    "openai": "",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "deepseek": "https://api.deepseek.com/v1",
    "openai_compatible": "",
}


def _provider_index(value: str) -> int:
    return PROVIDERS.index(value) if value in PROVIDERS else 0


def render() -> None:
    page_title("Configuracion", "Centro unico de parametros de Wally")

    tab_general, tab_sql, tab_ia, tab_crm, tab_presupuesto, tab_traslados, tab_local = st.tabs(
        ["General", "Conexion SQL", "Mar-IA", "CRM", "Presupuesto", "Traslados", "Datos locales"]
    )

    with tab_general:
        section_title("Identidad")
        st.write(f"Nombre de la app: **{env_value('APP_NAME', 'WallyAgent')}**")
        st.write("Agente IA: **Mar-IA**")
        st.write(f"Ruta de instalacion esperada: `{APP_DIR}`")
        st.write("Ruta oficial V4: `C:\\Apps\\Wally4`")

    with tab_sql:
        section_title("Conexion SQL Server")
        st.caption("La version inicial lee valores desde el archivo .env. En la version comercial se editara desde esta pantalla.")
        env_file = APP_DIR / ".env"
        st.write(f"Archivo .env: `{env_file}`")
        if st.button("Probar conexion SQL"):
            ok, message = db.test_connection()
            if ok:
                st.success(message)
            else:
                st.error(message)
        st.write("Vistas oficiales:")
        st.code(
            "\n".join(
                [
                    db.VIEW_VENTAS,
                    db.VIEW_EXISTENCIA,
                    db.VIEW_ENTRADAS,
                    db.VIEW_CRM,
                    db.VIEW_AUDITORIA_CAMBIO_VENDEDOR,
                ]
            )
        )

    with tab_ia:
        section_title("Proveedor IA de Mar-IA")
        st.caption("Configura el modelo principal y un modelo de respaldo. Las claves se guardan en SQLite local de Wally.")

        current_provider = get_param("maria_ai_provider", os.getenv("MARIA_AI_PROVIDER", "openai"))
        current_backup_provider = get_param("maria_backup_provider", "openai")

        with st.form("maria_provider_form"):
            provider = st.selectbox(
                "Proveedor principal",
                PROVIDERS,
                index=_provider_index(current_provider),
                format_func=lambda value: PROVIDER_LABELS.get(value, value),
            )
            model = st.text_input(
                "Modelo principal",
                value=get_param("maria_model", DEFAULT_MODELS.get(provider, "")) or DEFAULT_MODELS.get(provider, ""),
            )
            base_url = st.text_input(
                "URL base principal",
                value=get_param("maria_base_url", DEFAULT_URLS.get(provider, "")) or DEFAULT_URLS.get(provider, ""),
            )
            has_main_key = bool(get_param("maria_api_key", "") or os.getenv("MARIA_API_KEY") or os.getenv("OPENAI_API_KEY"))
            if has_main_key:
                st.caption("API Key principal: configurada. Escribe una nueva solo si deseas reemplazarla.")
            api_key = st.text_input("API Key principal", value="", type="password")

            st.markdown("#### Respaldo")
            backup_provider = st.selectbox(
                "Proveedor de respaldo",
                PROVIDERS,
                index=_provider_index(current_backup_provider),
                format_func=lambda value: PROVIDER_LABELS.get(value, value),
            )
            backup_model = st.text_input(
                "Modelo de respaldo opcional",
                value=get_param("maria_backup_model", DEFAULT_MODELS.get(backup_provider, "")) or DEFAULT_MODELS.get(backup_provider, ""),
            )
            backup_base_url = st.text_input(
                "URL base de respaldo",
                value=get_param("maria_backup_base_url", DEFAULT_URLS.get(backup_provider, "")) or DEFAULT_URLS.get(backup_provider, ""),
            )
            has_backup_key = bool(get_param("maria_backup_api_key", "") or os.getenv("OPENAI_API_KEY"))
            if has_backup_key:
                st.caption("API Key de respaldo: configurada. Escribe una nueva solo si deseas reemplazarla.")
            backup_api_key = st.text_input("API Key de respaldo", value="", type="password")

            st.markdown("#### Transcripcion de audio")
            transcription_provider = st.selectbox(
                "Proveedor principal de transcripcion",
                TRANSCRIPTION_PROVIDERS,
                index=TRANSCRIPTION_PROVIDERS.index(
                    get_param("maria_transcription_provider", os.getenv("MARIA_TRANSCRIPTION_PROVIDER", "openai"))
                    if get_param("maria_transcription_provider", os.getenv("MARIA_TRANSCRIPTION_PROVIDER", "openai")) in TRANSCRIPTION_PROVIDERS
                    else "openai"
                ),
                format_func=lambda value: "OpenAI / compatible" if value == "openai" else "Local faster-whisper",
            )
            transcription_model = st.text_input(
                "Modelo de transcripcion principal",
                value=get_param("maria_transcription_model", os.getenv("MARIA_TRANSCRIPTION_MODEL", "whisper-1")) or "whisper-1",
                help="Para OpenAI normalmente usa whisper-1.",
            )
            local_transcription_enabled = st.checkbox(
                "Usar faster-whisper local como respaldo",
                value=(get_param("maria_local_transcription_enabled", os.getenv("MARIA_LOCAL_TRANSCRIPTION_ENABLED", "yes")).lower() in {"yes", "si", "true", "1"}),
            )
            local_transcription_model = st.selectbox(
                "Modelo local faster-whisper",
                ["tiny", "base", "small", "medium", "large-v3"],
                index=["tiny", "base", "small", "medium", "large-v3"].index(
                    get_param("maria_local_transcription_model", os.getenv("MARIA_LOCAL_TRANSCRIPTION_MODEL", "small"))
                    if get_param("maria_local_transcription_model", os.getenv("MARIA_LOCAL_TRANSCRIPTION_MODEL", "small")) in ["tiny", "base", "small", "medium", "large-v3"]
                    else "small"
                ),
                help="Recomendado para este servidor: small. Probar medium si se necesita mas precision.",
            )

            st.markdown("#### Personalidad y reglas")
            personality_prompt = st.text_area(
                "Prompt de personalidad de Mar-IA",
                value=get_param("maria_personality_prompt", DEFAULT_MARIA_PERSONALITY_PROMPT),
                height=260,
                help="Este texto define tono, limites y reglas de Mar-IA. No escribas claves secretas aqui.",
            )

            saved = st.form_submit_button("Guardar configuracion Mar-IA")

        if saved:
            set_param("maria_ai_provider", provider, "Proveedor principal de IA para Mar-IA")
            set_param("maria_model", model.strip() or DEFAULT_MODELS.get(provider, ""), "Modelo principal de IA para Mar-IA")
            set_param("maria_base_url", base_url.strip(), "URL base opcional del proveedor principal de Mar-IA")
            if api_key.strip():
                set_param("maria_api_key", api_key.strip(), "API key principal de Mar-IA")
            set_param("maria_backup_provider", backup_provider, "Proveedor secundario de IA para Mar-IA")
            set_param("maria_backup_model", backup_model.strip() or DEFAULT_MODELS.get(backup_provider, ""), "Modelo secundario de IA para Mar-IA")
            set_param("maria_backup_base_url", backup_base_url.strip(), "URL base opcional del proveedor secundario de Mar-IA")
            if backup_api_key.strip():
                set_param("maria_backup_api_key", backup_api_key.strip(), "API key secundaria de Mar-IA")
            set_param("maria_transcription_provider", transcription_provider, "Proveedor principal de transcripcion de audio")
            set_param("maria_transcription_model", transcription_model.strip() or "whisper-1", "Modelo principal de transcripcion de audio")
            set_param(
                "maria_local_transcription_enabled",
                "yes" if local_transcription_enabled else "no",
                "Activar respaldo local con faster-whisper",
            )
            set_param("maria_local_transcription_model", local_transcription_model, "Modelo local de faster-whisper")
            set_param(
                "maria_personality_prompt",
                personality_prompt.strip() or DEFAULT_MARIA_PERSONALITY_PROMPT,
                "Prompt editable de personalidad y reglas de Mar-IA",
            )
            st.success("Configuracion de Mar-IA guardada. Reinicia los servicios para que Telegram tome los cambios.")

    with tab_crm:
        section_title("Parametros CRM")
        quota = int(get_param("crm_cuota_diaria_vendedor", "60") or 60)
        new_quota = st.number_input("Cuota diaria igual para todos los vendedores", min_value=1, max_value=500, value=quota)
        if st.button("Guardar cuota CRM"):
            set_param("crm_cuota_diaria_vendedor", str(int(new_quota)), "Cuota diaria igual para todos los vendedores")
            st.success("Cuota CRM guardada.")
        st.write("Reglas activas:")
        st.markdown(
            """
            - El sistema sugiere clientes y el administrador aprueba.
            - Prioridad: mas dias sin compra, mayor venta historica, mayor cantidad de facturas, celular primero.
            - Cliente asignado a una sola sucursal: sucursal preferida.
            - Vendedor responsable: vendedor de la ultima factura.
            """
        )

    with tab_presupuesto:
        presupuesto.render_import_admin()

    with tab_traslados:
        section_title("Prioridad de tiendas para traslados")
        st.caption("Prioridad 1 recibe primero. Prioridad 0 excluye la tienda: no recibe y no envia producto.")
        try:
            branch_priorities = load_branch_priorities(official_branches())
        except Exception as exc:
            st.error("No se pudieron cargar tiendas desde la vista de existencias.")
            st.exception(exc)
            branch_priorities = read_table("traslado_prioridad_sucursal").rename(
                columns={"sucursal": "Sucursal", "prioridad": "Prioridad"}
            )

        edited_priorities = st.data_editor(
            branch_priorities[["Sucursal", "Prioridad"]],
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            column_config={
                "Sucursal": st.column_config.TextColumn("Sucursal", disabled=True),
                "Prioridad": st.column_config.NumberColumn("Prioridad", min_value=0, step=1, format="%d"),
            },
            key="traslado_prioridad_editor",
        )
        if st.button("Guardar prioridades de traslados"):
            save_branch_priorities(edited_priorities)
            st.success("Prioridades de traslados guardadas.")

    with tab_local:
        section_title("SQLite local")
        st.write(f"Base local: `{sqlite_path()}`")
        for table_name in [
            "app_parametros",
            "crm_asignaciones",
            "crm_gestiones",
            "meta_sucursal",
            "meta_vendedor",
            "meta_linea",
            "pto_sucursal",
            "pto_vendedor",
            "pto_linea_sucursal",
            "presupuesto_importacion_log",
            "presupuesto_importacion_error",
            "traslado_prioridad_sucursal",
        ]:
            with st.expander(table_name):
                display_table(read_table(table_name), height=260, show_total=False)
