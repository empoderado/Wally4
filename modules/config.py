from __future__ import annotations

import streamlit as st

from services.local_store import read_table
from services.paths import APP_DIR, sqlite_path
from services.env import env_list, env_value
from services import db
from services.ui import page_title, section_title


def render() -> None:
    page_title("Configuracion", "Parametros locales de WallyAgent")
    section_title("Estado de entorno")
    c1, c2, c3 = st.columns(3)
    c1.metric("APP_ENV", env_value("APP_ENV", "production"))
    c2.metric("USE_MOCK_DATA", env_value("USE_MOCK_DATA", "no"))
    c3.metric("Puerto", env_value("APP_PORT", "8503"))

    ok, message = db.test_connection()
    if ok:
        st.success(message)
    else:
        st.warning(message)

    section_title("Rutas")
    st.write(f"App: `{APP_DIR}`")
    st.write(f"SQLite: `{sqlite_path()}`")

    section_title("SQL Server")
    st.write(f"Servidor: `{env_value('SQL_SERVER', 'No configurado')}`")
    st.write(f"Base de datos: `{env_value('SQL_DATABASE', 'No configurado')}`")
    st.write(f"Driver: `{env_value('SQL_DRIVER', 'No configurado')}`")
    st.write(f"Trusted Connection: `{env_value('SQL_TRUSTED_CONNECTION', 'yes')}`")

    section_title("Telegram")
    token_configured = "Si" if env_value("TELEGRAM_BOT_TOKEN") else "No"
    allowed = env_list("TELEGRAM_ALLOWED_CHAT_IDS")
    st.write(f"Token configurado: `{token_configured}`")
    st.write(f"Chats permitidos: `{', '.join(sorted(allowed)) if allowed else 'Todos mientras no se configure restriccion'}`")
    st.caption("Para iniciar o reiniciar WallyAgent y sus canales ejecute `01_Iniciar_o_Reiniciar_Servicios_WallyAgent.cmd` despues de configurar TELEGRAM_BOT_TOKEN en .env.")
    section_title("Parametros")
    st.dataframe(read_table("app_parametros"), use_container_width=True, hide_index=True)
