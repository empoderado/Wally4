from __future__ import annotations

import os

import streamlit as st

from memory.store import memory_snapshot, recent_conversations, remember
from modules import presupuesto
from services import db
from services.branches import branch_config_frame, discover_official_branches, save_branch_config
from services.env import env_value
from services.local_store import DEFAULT_MARIA_PERSONALITY_PROMPT, get_param, read_table, set_param
from services.maria_ai import configuration_status
from services.paths import APP_DIR, sqlite_path
from services.telegram import DEFAULT_API_URL, get_telegram_config, normalize_api_url, test_telegram_connection
from services.transfers import load_branch_priorities, official_branches, save_branch_priorities
from services.ui import display_table, page_title, section_title, code_footer
from services.catalog import get_code


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


def _masked_parameter_table():
    frame = read_table("app_parametros")
    if frame.empty or "clave" not in frame.columns or "valor" not in frame.columns:
        return frame
    sensitive = frame["clave"].str.lower().str.contains("token|api_key|password|secret", regex=True)
    frame.loc[sensitive, "valor"] = "********"
    return frame


def render() -> None:
    page_title("Configuracion", "Centro unico de parametros de Wally")

    tab_general, tab_sql, tab_ia, tab_telegram, tab_crm, tab_sucursales, tab_presupuesto, tab_traslados, tab_rotacion, tab_local, tab_colaboradores = st.tabs(
        ["General", "Conexion SQL", "Mar-IA", "Telegram", "CRM", "Sucursales", "Presupuesto", "Traslados", "Rotación Derivada", "Datos locales", "Colaboradores"]
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
        col_conn, col_cache = st.columns(2)
        with col_conn:
            if st.button("Probar conexion SQL", use_container_width=True):
                ok, message = db.test_connection()
                if ok:
                    st.success(message)
                else:
                    st.error(message)
        with col_cache:
            if st.button("Limpiar cache de consultas", use_container_width=True):
                db.clear_query_cache()
                st.success("Cache de consultas limpiada. Se forzara la recarga de datos reales.")
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
        ai_status = configuration_status()
        if ai_status["configured"]:
            st.success(f"IA configurada: {ai_status['provider']} / {ai_status['model']}")
        else:
            st.warning("La API key de Mar-IA no esta guardada en esta instancia. Las respuestas usaran el motor local.")

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
                value=get_param("maria_transcription_model", os.getenv("MARIA_TRANSCRIPTION_MODEL", "gpt-4o-transcribe")) or "gpt-4o-transcribe",
                help="Recomendado para mayor precision: gpt-4o-transcribe.",
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
            set_param("maria_transcription_model", transcription_model.strip() or "gpt-4o-transcribe", "Modelo principal de transcripcion de audio")
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

        _render_maria_memory_admin()

    with tab_telegram:
        section_title("Conexion de Mar-IA con Telegram")
        st.caption(
            "Administra el token, la URL y los permisos del canal. "
            "El proceso de Telegram recarga los cambios automaticamente."
        )
        telegram_config = get_telegram_config()

        status_1, status_2, status_3 = st.columns(3)
        status_1.metric("Canal", "Activo" if telegram_config.enabled else "Inactivo")
        status_2.metric("Token", "Configurado" if telegram_config.token else "Pendiente")
        status_3.metric(
            "Acceso",
            "Todos" if telegram_config.allow_all_chats else f"{len(telegram_config.allowed_chat_ids)} chat(s)",
        )

        with st.expander("Parametros requeridos", expanded=True):
            st.markdown(
                """
                1. **Token del bot:** proporcionado por BotFather.
                2. **URL base:** normalmente `https://api.telegram.org`.
                3. **Modo de acceso:** restringido o permitido para todos.
                4. **IDs autorizados:** IDs de usuarios o grupos separados por coma.
                """
            )

        with st.form("telegram_connection_form"):
            telegram_enabled = st.checkbox("Activar canal Telegram", value=telegram_config.enabled)
            st.text_input(
                "Token actual",
                value="Configurado" if telegram_config.token else "No configurado",
                disabled=True,
            )
            telegram_token = st.text_input(
                "Nuevo token del bot",
                value="",
                type="password",
                help="Dejalo vacio para conservar el token actual.",
            )
            telegram_api_url = st.text_input(
                "URL base de Telegram",
                value=telegram_config.api_url or DEFAULT_API_URL,
                help=(
                    "Normalmente https://api.telegram.org. Si pega una URL completa "
                    "/botTOKEN/getMe, Wally conservara solamente la URL base."
                ),
            )
            access_mode = st.radio(
                "Acceso permitido",
                ["Solo chats autorizados", "Todos los chats"],
                index=1 if telegram_config.allow_all_chats else 0,
                help="Se recomienda restringir el acceso a la informacion empresarial.",
            )
            telegram_allowed_ids = st.text_area(
                "IDs de chat autorizados",
                value=", ".join(sorted(telegram_config.allowed_chat_ids)),
                placeholder="123456789, -1001234567890",
            )
            remove_token = st.checkbox("Eliminar el token guardado")
            save_telegram = st.form_submit_button("Guardar conexion")
            test_telegram = st.form_submit_button("Probar conexion")

        effective_token = telegram_token.strip() or telegram_config.token
        normalized_url = normalize_api_url(telegram_api_url)
        parsed_ids = {
            item.strip()
            for item in telegram_allowed_ids.replace("\n", ",").split(",")
            if item.strip()
        }
        invalid_ids = sorted(item for item in parsed_ids if not item.lstrip("-").isdigit())
        allow_all = access_mode == "Todos los chats"

        if test_telegram:
            if remove_token or not effective_token:
                st.error("Ingrese un token para probar la conexion.")
            elif not normalized_url.lower().startswith(("https://", "http://")):
                st.error("La URL base debe comenzar con https:// o http://.")
            else:
                ok, message = test_telegram_connection(effective_token, normalized_url)
                if ok:
                    st.success(message)
                else:
                    st.error(f"No fue posible conectar: {message}")

        if save_telegram:
            errors = []
            if telegram_enabled and remove_token:
                errors.append("No puede activar Telegram y eliminar el token al mismo tiempo.")
            if telegram_enabled and not effective_token:
                errors.append("Debe ingresar el token para activar Telegram.")
            if not normalized_url.lower().startswith(("https://", "http://")):
                errors.append("La URL base debe comenzar con https:// o http://.")
            if invalid_ids:
                errors.append("IDs de chat invalidos: " + ", ".join(invalid_ids))
            if telegram_enabled and not allow_all and not parsed_ids:
                errors.append("Agregue un ID autorizado o seleccione acceso para todos.")

            if errors:
                for error in errors:
                    st.error(error)
            else:
                set_param("telegram_enabled", "yes" if telegram_enabled else "no", "Activar canal Telegram de Mar-IA")
                set_param("telegram_api_url", normalized_url, "URL base editable de Telegram")
                set_param("telegram_allow_all_chats", "yes" if allow_all else "no", "Permitir cualquier chat")
                set_param(
                    "telegram_allowed_chat_ids",
                    ",".join(sorted(parsed_ids)),
                    "IDs autorizados para consultar Mar-IA",
                )
                if remove_token:
                    set_param("telegram_bot_token", "", "Token del bot de Telegram")
                elif telegram_token.strip():
                    set_param("telegram_bot_token", telegram_token.strip(), "Token del bot de Telegram")
                st.success("Conexion de Telegram guardada.")
                st.rerun()

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

    with tab_sucursales:
        section_title("Sucursales incluidas en Wally")
        st.caption(
            "Las sucursales activas participan en todos los reportes, indicadores, gráficos y cálculos. "
            "Desactivar una sucursal no elimina sus datos."
        )
        try:
            branch_frame = branch_config_frame(discover_official_branches())
        except Exception as exc:
            st.error("No se pudo cargar el catálogo de sucursales.")
            st.exception(exc)
            branch_frame = branch_config_frame([])

        edited_branches = st.data_editor(
            branch_frame,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            column_config={
                "Sucursal": st.column_config.TextColumn("Sucursal", disabled=True),
                "Activa": st.column_config.CheckboxColumn(
                    "Incluir en Wally",
                    help="Activa: se incluye. Inactiva: se excluye de reportes e indicadores.",
                    default=True,
                ),
            },
            key="app_sucursal_config_editor",
        )
        active_count = int(edited_branches["Activa"].fillna(False).astype(bool).sum()) if not edited_branches.empty else 0
        st.caption(f"Sucursales activas: {active_count} de {len(edited_branches)}")
        if st.button("Guardar configuración de sucursales", type="primary"):
            save_branch_config(edited_branches)
            db.clear_query_cache()
            st.success("Configuración guardada. Los reportes ya utilizan únicamente las sucursales activas.")
            st.rerun()

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

    with tab_rotacion:
        section_title("Configuración de Rotación Derivada")
        st.caption("Ajusta los umbrales globales por defecto para clasificar las referencias de inventario.")

        try:
            current_vel = float(get_param("rot_threshold_vel", "1.0"))
        except ValueError:
            current_vel = 1.0

        try:
            current_inv = int(get_param("rot_threshold_inv", "30"))
        except ValueError:
            current_inv = 30

        with st.form("rot_thresholds_form"):
            vel_threshold_admin = st.slider(
                "Umbral de Velocidad por Defecto (% de entradas / día)",
                0.0, 10.0, current_vel, 0.1,
                key="rot_threshold_vel_admin"
            )
            inv_threshold_admin = st.slider(
                "Umbral de Inventario por Defecto (% de entradas)",
                0, 100, current_inv, 5,
                key="rot_threshold_inv_admin"
            )

            submitted_rot = st.form_submit_button("Guardar Umbrales de Rotación")
            if submitted_rot:
                set_param("rot_threshold_vel", f"{vel_threshold_admin:.2f}", "Umbral de velocidad de venta por defecto (% entradas/dia)")
                set_param("rot_threshold_inv", str(inv_threshold_admin), "Umbral de inventario remanente por defecto (% entradas)")
                st.success("Umbrales de rotación guardados exitosamente.")

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
            "app_sucursal_config",
        ]:
            with st.expander(table_name):
                table = _masked_parameter_table() if table_name == "app_parametros" else read_table(table_name)
                display_table(table, height=260, show_total=False)

    with tab_colaboradores:
        _render_colaboradores_turnos()


def _render_maria_memory_admin() -> None:
    section_title("Memoria e historial de Mar-IA")
    history_tab, memory_tab = st.tabs(["Historial", "Memoria"])

    with history_tab:
        history = recent_conversations(limit=50, user_id="local")
        if history.empty:
            st.caption("Aun no hay conversaciones registradas.")
        else:
            st.dataframe(history, use_container_width=True, hide_index=True)

    with memory_tab:
        snapshot = memory_snapshot(user_id="local")
        short_tab, medium_tab, permanent_tab, add_tab = st.tabs(
            ["Corto plazo", "Mediano plazo", "Permanente", "Agregar"]
        )
        with short_tab:
            if snapshot.short_term.empty:
                st.caption("Sin memoria de corto plazo.")
            else:
                st.dataframe(snapshot.short_term, use_container_width=True, hide_index=True)
        with medium_tab:
            if snapshot.medium_term.empty:
                st.caption("Sin memoria de mediano plazo.")
            else:
                st.dataframe(snapshot.medium_term, use_container_width=True, hide_index=True)
        with permanent_tab:
            if snapshot.permanent.empty:
                st.caption("Sin memoria permanente.")
            else:
                st.dataframe(snapshot.permanent, use_container_width=True, hide_index=True)
        with add_tab:
            with st.form("config_maria_memory_form", clear_on_submit=True):
                memory_type = st.selectbox(
                    "Tipo de memoria",
                    ["medium", "permanent"],
                    format_func=lambda value: "Mediano plazo" if value == "medium" else "Permanente",
                    key="config_maria_memory_type",
                )
                key_text = st.text_input(
                    "Clave",
                    placeholder="preferred_branch",
                    key="config_maria_memory_key",
                )
                value_text = st.text_area(
                    "Valor",
                    placeholder="OAKLAND",
                    key="config_maria_memory_value",
                )
                days = st.number_input(
                    "Dias de vigencia",
                    min_value=1,
                    max_value=3650,
                    value=90,
                    disabled=memory_type == "permanent",
                    key="config_maria_memory_days",
                )
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


def _render_colaboradores_turnos() -> None:
    import pandas as pd
    section_title("Turnos de Colaboradores")
    st.caption("Administra los turnos de trabajo (Diurno, Mixto, Completo o Nocturno) de los colaboradores del ERP.")

    try:
        df = db.read_sql("SELECT * FROM dbo.VwColaboradoresTurno ORDER BY ABS(CODIGO) ASC")
    except Exception as exc:
        st.error(f"Error al cargar vista de colaboradores: {exc}")
        return

    if df.empty:
        st.warning("No se encontraron colaboradores.")
        return

    # Filter by active status
    col_filter, col_download = st.columns([0.5, 0.5])
    with col_filter:
        estado_filter = st.selectbox(
            "Filtrar por estado del colaborador",
            options=["Todos", "Solo activos", "Solo inactivos"],
            index=1,  # Default to Solo activos
            key="colab_estado_filter"
        )

    with col_download:
        # Filter active sellers (Cargo == 'Vendedor' and Activo == True)
        df_vendedores = df[(df["Activo"] == True) & (df["Cargo"].str.strip().str.upper() == "VENDEDOR")].copy()
        df_excel = df_vendedores[["CODIGO", "Nombre", "Cargo", "Sucursal", "Turno"]].copy()
        df_excel.columns = ["Codigo", "Colaborador", "Cargo", "Sucursal", "Turno"]
        
        import io
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_excel.to_excel(writer, index=False, sheet_name='Vendedores')
        excel_data = output.getvalue()
        
        st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
        st.download_button(
            label="📥 Descargar Excel Vendedores Activos",
            data=excel_data,
            file_name="Vendedores_Activos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="download_vendedores_excel"
        )

    if estado_filter == "Solo activos":
        df_filtered = df[df["Activo"] == True]
    elif estado_filter == "Solo inactivos":
        df_filtered = df[df["Activo"] == False]
    else:
        df_filtered = df

    st.write("### Listado de Colaboradores y Turnos")
    if df_filtered.empty:
        st.info("No hay colaboradores que coincidan con el filtro seleccionado.")
    else:
        df_display = df_filtered.copy()
        if "Fecha Creacion" in df_display.columns:
            df_display["Fecha Creacion"] = pd.to_datetime(df_display["Fecha Creacion"]).dt.strftime("%Y-%m-%d %H:%M")
        if "Fecha de alta" in df_display.columns:
            df_display["Fecha de alta"] = pd.to_datetime(df_display["Fecha de alta"]).dt.strftime("%Y-%m-%d %H:%M").fillna("Sin ventas")
        if "Activo" in df_display.columns:
            df_display["Activo"] = df_display["Activo"].map(lambda x: "Activo" if x else "Inactivo")

        # Format values to match display_table aesthetics
        from services.ui import _format_value
        formatted = df_display.copy()
        for col in formatted.columns:
            formatted[col] = formatted[col].map(lambda val, c=col: _format_value(val, c))
        
        numeric_columns = [col for col in df_filtered.columns if pd.api.types.is_numeric_dtype(df_filtered[col])]
        styler = formatted.style
        if numeric_columns:
            styler = styler.set_properties(subset=numeric_columns, **{"text-align": "right"})
            
        event = st.dataframe(
            styler,
            use_container_width=True,
            hide_index=True,
            height=350,
            on_select="rerun",
            selection_mode="single-row",
            key="colab_table"
        )
        
        # Handle selection
        selected_row_idx = None
        if event and hasattr(event, "selection") and "rows" in event.selection and event.selection["rows"]:
            selected_row_idx = event.selection["rows"][0]
            
        if selected_row_idx is not None and selected_row_idx < len(df_filtered):
            selected_codigo = int(df_filtered.iloc[selected_row_idx]["CODIGO"])
            st.session_state["selected_colab_code_state"] = selected_codigo

    st.markdown("---")
    st.write("### Asignar o Cambiar Turno y Estado")

    colab_options = []
    for _, row in df_filtered.iterrows():
        cod = int(row["CODIGO"])
        name = str(row["Nombre"])
        cargo = str(row["Cargo"])
        status_label = "Activo" if row["Activo"] else "Inactivo"
        colab_options.append((cod, f"{name} (Código: {cod} - Puesto: {cargo} - {status_label})"))

    if not colab_options:
        st.warning("No hay colaboradores disponibles para asignar turnos o cambiar estado.")
        return

    colab_ids = [opt[0] for opt in colab_options]

    col_search, col_select = st.columns([0.35, 0.65])
    with col_search:
        search_code = st.text_input(
            "🔍 Buscar por código de asesor",
            placeholder="Ej: 94, 95...",
            key="colab_search_code_input"
        )
        if search_code.strip():
            clean_search = search_code.strip()
            matched_search = df[df["CODIGO"].astype(str).str.strip() == clean_search]
            if not matched_search.empty:
                found_code = int(matched_search.iloc[0]["CODIGO"])
                st.session_state["selected_colab_code_state"] = found_code
                st.caption(f"✓ Encontrado: {matched_search.iloc[0]['Nombre']}")
            else:
                st.caption("⚠️ No se encontró colaborador con ese código.")

    # Calculate default select index based on selection state
    default_colab_id = st.session_state.get("selected_colab_code_state")
    if default_colab_id in colab_ids:
        default_select_idx = colab_ids.index(default_colab_id)
    else:
        default_select_idx = 0

    with col_select:
        colab_selected = st.selectbox(
            "Seleccione el colaborador",
            options=colab_ids,
            index=default_select_idx,
            format_func=lambda x: next(opt[1] for opt in colab_options if opt[0] == x),
            key="selected_colab_turno_box"
        )
        st.session_state["selected_colab_code_state"] = colab_selected

    current_turno = "Diurno"
    current_activo = True
    matched = df[df["CODIGO"] == colab_selected]
    if not matched.empty:
        current_turno = str(matched.iloc[0]["Turno"])
        current_activo = bool(matched.iloc[0]["Activo"])

    turno_options = ["Diurno", "Mixto", "Completo", "Nocturno"]
    default_idx = turno_options.index(current_turno) if current_turno in turno_options else 0

    col_t, col_e = st.columns(2)
    with col_t:
        new_turno = st.selectbox(
            "Turno de trabajo",
            options=turno_options,
            index=default_idx,
            key="new_colab_turno"
        )
    with col_e:
        estado_options = ["Activo", "Inactivo"]
        default_est_idx = 0 if current_activo else 1
        new_estado = st.selectbox(
            "Estado del colaborador",
            options=estado_options,
            index=default_est_idx,
            key="new_colab_estado"
        )

    if st.button("Guardar Cambios de Colaborador", use_container_width=True):
        try:
            is_active = (new_estado == "Activo")
            db.save_colaborador_turno(colab_selected, new_turno)
            db.save_colaborador_estado(colab_selected, is_active)
            st.success(f"Turno '{new_turno}' y Estado '{new_estado}' guardados exitosamente.")
            st.rerun()
        except Exception as exc:
            st.error(f"Error al guardar cambios: {exc}")

    # Code footer
    st.markdown("---")
    code_footer(*get_code("colaboradores", "detail_table"))
