from __future__ import annotations

import streamlit as st

from modules import asesores, gerencia_asesores, auditoria, config_wally, crm, dashboard_wally, embarques, existencias, gerencia, maria_agent, presupuesto, reportes, rotacion_analisis, training, traslados
from services.env import env_value
from services.local_store import init_store
from services.paths import APP_DIR


APP_ICON = APP_DIR / "assets" / "WallyAgent_icon.png"
if not APP_ICON.exists():
    APP_ICON = APP_DIR / "assets" / "Wallyicono.png"

APP_NAME = env_value("APP_NAME", "WallyAgent")

st.set_page_config(
    page_title=APP_NAME,
    page_icon=str(APP_ICON),
    layout="wide",
    initial_sidebar_state="collapsed",
)


CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
* {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
}
:root {
    --wally-charcoal: #0e0c15;
    --wally-charcoal-2: #181222;
    --wally-red: #6c1c36;
    --wally-blue: #3b82f6;
    --wally-teal: #0f766e;
    --wally-amber: #d97706;
    --wally-ink: #0f172a;
    --wally-muted: #64748b;
    --wally-bg: #fcfbfa;
    --wally-surface: #ffffff;
    --wally-surface-2: #f8fafc;
    --wally-border: #e2e8f0;
    --wally-shadow: 0 6px 20px rgba(108, 28, 54, 0.04), 0 2px 8px rgba(0, 0, 0, 0.02);
}
.stApp {
    background:
        linear-gradient(180deg, #ffffff 0, var(--wally-bg) 245px),
        var(--wally-bg);
    color: var(--wally-ink);
}
#MainMenu, footer, header, [data-testid="stToolbar"], [data-testid="stDecoration"] {
    visibility: hidden;
    height: 0;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--wally-charcoal) 0%, var(--wally-charcoal-2) 100%);
    border-right: 1px solid rgba(255,255,255,.08);
    min-width: 300px !important;
    max-width: 320px !important;
}
[data-testid="stSidebarContent"],
[data-testid="stSidebar"] > div:first-child {
    height: 100vh;
    overflow-y: scroll !important;
    overflow-x: hidden;
    scrollbar-gutter: stable;
    scrollbar-width: auto;
    scrollbar-color: rgba(255,255,255,.55) rgba(255,255,255,.10);
}
[data-testid="stSidebarContent"]::-webkit-scrollbar,
[data-testid="stSidebar"] > div:first-child::-webkit-scrollbar {
    width: 12px;
}
[data-testid="stSidebarContent"]::-webkit-scrollbar-track,
[data-testid="stSidebar"] > div:first-child::-webkit-scrollbar-track {
    background: rgba(255,255,255,.10);
}
[data-testid="stSidebarContent"]::-webkit-scrollbar-thumb,
[data-testid="stSidebar"] > div:first-child::-webkit-scrollbar-thumb {
    background: rgba(255,255,255,.55);
    border: 3px solid transparent;
    border-radius: 999px;
    background-clip: padding-box;
}
[data-testid="stSidebarContent"]::-webkit-scrollbar-thumb:hover,
[data-testid="stSidebar"] > div:first-child::-webkit-scrollbar-thumb:hover {
    background: rgba(255,255,255,.75);
    border: 3px solid transparent;
    background-clip: padding-box;
}
[data-testid="stSidebar"][aria-expanded="false"] {
    min-width: 0 !important;
    max-width: 0 !important;
    width: 0 !important;
}
[data-testid="stSidebarCollapsedControl"] {
    left: .75rem;
    top: .75rem;
    background: #ffffff;
    border: 1px solid var(--wally-border);
    border-radius: 8px;
    box-shadow: var(--wally-shadow);
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #f8fafc !important;
    font-size: .86rem !important;
}
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea,
[data-testid="stSidebar"] [data-baseweb="select"] * {
    color: #0f172a !important;
    font-size: .86rem !important;
}
[data-testid="stSidebar"] [role="radiogroup"] {
    gap: 4px;
}
[data-testid="stSidebar"] [role="radiogroup"] label {
    background: rgba(255,255,255,.045);
    border: 1px solid rgba(255,255,255,.07);
    border-radius: 8px;
    padding: 6px 10px;
    min-height: 34px;
    transition: background 0.2s ease, border-color 0.2s ease;
}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {
    background: rgba(255,255,255,.09);
    border-color: rgba(255,255,255,.15);
}
.block-container {
    max-width: 100%;
    padding: 1.05rem 1rem 2rem 1rem;
}
h1 {
    color: var(--wally-ink);
    font-size: 2.05rem;
    line-height: 1.05;
    margin: 0 0 .18rem 0;
    font-weight: 780;
    letter-spacing: 0;
}
.wally-brand {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
}
.wally-brand-mark {
    width: 34px;
    height: 34px;
    border-radius: 8px;
    display: grid;
    place-items: center;
    background: #ffffff;
    color: var(--wally-red);
    font-weight: 900;
    box-shadow: 0 7px 22px rgba(108, 28, 54, .35);
}
.wally-brand-title {
    color: #ffffff;
    font-size: 1.05rem;
    font-weight: 780;
    line-height: 1.05;
}
.wally-brand-subtitle {
    color: #cbd5e1;
    font-size: .75rem;
    margin-top: 2px;
}
.wally-sidebar-status {
    background: rgba(255,255,255,.08);
    border: 1px solid rgba(255,255,255,.12);
    border-radius: 8px;
    padding: 9px 10px;
    margin: 10px 0 12px 0;
}
.wally-sidebar-status div {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    color: #dbeafe;
    font-size: .75rem;
    line-height: 1.5;
}
.wally-page-heading {
    margin: .1rem 0 1rem 0;
}
.wally-eyebrow {
    color: var(--wally-red);
    font-size: .72rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: .08em;
    margin-bottom: 4px;
}
.wally-subtitle {
    color: var(--wally-muted);
    font-size: .98rem;
    margin-bottom: .1rem;
}
.wally-card {
    position: relative;
    background: var(--wally-surface);
    border: 1px solid var(--wally-border);
    border-radius: 12px;
    padding: 13px 13px 12px 14px;
    box-shadow: var(--wally-shadow);
    min-height: 112px;
    height: 112px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    text-align: center;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.wally-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 10px 24px rgba(108, 28, 54, 0.08), 0 4px 12px rgba(0, 0, 0, 0.03);
}
.wally-card::before {
    content: "";
    position: absolute;
    left: 14px;
    right: 14px;
    top: 0;
    width: auto;
    height: 4px;
    background: var(--wally-blue);
    border-radius: 0 0 6px 6px;
}
.wally-card-good::before { background: var(--wally-teal); }
.wally-card-bad::before { background: var(--wally-red); }
.wally-card-neutral::before { background: var(--wally-blue); }
.wally-label {
    color: var(--wally-muted);
    font-size: .68rem;
    font-weight: 850;
    text-transform: uppercase;
    letter-spacing: .03em;
    line-height: 1.12;
    min-height: 28px;
    margin-bottom: .35rem;
    overflow-wrap: anywhere;
    text-align: center;
}
.wally-value {
    color: var(--wally-ink);
    font-size: clamp(1.02rem, 1.35vw, 1.34rem);
    font-weight: 800;
    line-height: 1.08;
    overflow-wrap: anywhere;
    letter-spacing: 0;
    min-height: 31px;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
}
.wally-delta {
    font-size: .78rem;
    font-weight: 700;
    margin-top: .2rem;
    min-height: 18px;
    line-height: 1.15;
    text-align: center;
}
.wally-good { color: #057a55; }
.wally-bad { color: #dc2626; }
.wally-muted { color: var(--wally-muted); }
.wally-section-title {
    font-size: 1rem;
    font-weight: 800;
    color: var(--wally-ink);
    margin: 1rem 0 .55rem 0;
    display: flex;
    align-items: center;
    gap: 9px;
}
.wally-section-title::before {
    content: "";
    width: 8px;
    height: 22px;
    border-radius: 4px;
    background: var(--wally-red);
}
.wally-panel, .wally-page-shell {
    background: var(--wally-surface);
    border: 1px solid var(--wally-border);
    border-radius: 12px;
    padding: 12px 14px 8px 14px;
    box-shadow: var(--wally-shadow);
    margin-bottom: .85rem;
}
.wally-alert {
    background: #fff7ed;
    border: 1px solid #fed7aa;
    border-left: 5px solid #b7791f;
    border-radius: 8px;
    padding: 12px 14px;
    color: #7c2d12;
}
.wally-page-footer {
    margin-top: 18px;
    padding: 11px 12px;
    border: 1px solid var(--wally-border);
    border-radius: 8px;
    background: #ffffff;
    color: var(--wally-muted);
    font-size: .8rem;
    line-height: 1.45;
}
.wally-code-footer { color: #94a3b8; font-size: .66rem; line-height: 1.15; margin: 2px 0 10px 0; }
.wally-code-footer span { color: #64748b; font-weight: 800; margin-right: 5px; }
div[data-testid="stDataFrame"] {
    font-size: .82rem;
    border: 1px solid var(--wally-border);
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 16px rgba(16, 24, 40, .045);
}
.stDownloadButton button, .stButton button {
    border-radius: 8px;
    border: 1px solid var(--wally-red);
    background: var(--wally-red);
    color: #ffffff;
    font-weight: 700;
    min-height: 38px;
    transition: all 0.2s ease;
}
.stDownloadButton button:hover, .stButton button:hover {
    border-color: #58142a;
    background: #58142a;
    color: #ffffff;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(108, 28, 54, 0.25);
}
[data-testid="stMetric"] {
    background: var(--wally-surface);
    border: 1px solid var(--wally-border);
    border-radius: 12px;
    padding: 12px;
    box-shadow: var(--wally-shadow);
}
[data-testid="stExpander"] {
    border: 1px solid var(--wally-border);
    border-radius: 8px;
    background: #ffffff;
}
div[data-testid="stDateInput"] input,
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input {
    border-radius: 7px;
}
</style>
"""


PAGES = {
    "Resumen Ventas": dashboard_wally.render,
    "Asesores": asesores.render,
    "Gerencia Asesores": gerencia_asesores.render,
    "Gerencia Financiera": gerencia.render,
    "Gerencia Producto": gerencia.render_producto,
    "Rotacion Derivada": rotacion_analisis.render,
    "Existencias": existencias.render,
    "Embarques y Coleccion": embarques.render,
    "CRM": crm.render,
    "Traslados": traslados.render,
    "Auditoria": auditoria.render,
    "Presupuesto": presupuesto.render,
    "Reportes": reportes.render,
    "Mar-IA Agent": maria_agent.render,
    "Entrenamiento": training.render,
    "Configuracion": config_wally.render,
}

PAGE_VIEWS = {
    "Resumen Ventas": "dbo.VwFacturaConImpuesto",
    "Asesores": "dbo.VwFacturaConImpuesto | SQLite local: pto_vendedor",
    "Gerencia Asesores": "dbo.VwFacturaConImpuesto | SQLite local: pto_vendedor | dbo.VwColaboradoresTurno",
    "Gerencia Financiera": "dbo.VwFacturaConImpuesto",
    "Gerencia Producto": "dbo.VwFacturaConImpuesto | dbo.VwExistencia",
    "Rotacion Derivada": "dbo.VwFacturaConImpuesto | dbo.VwExistencia | dbo.VwEntradasInventario",
    "Existencias": "dbo.VwExistencia",
    "Embarques y Coleccion": "dbo.VwFacturaConImpuesto | dbo.VwExistencia",
    "CRM": "dbo.VwClienteResumenCRM",
    "Traslados": "dbo.VwExistencia | SQLite local: traslado_prioridad_sucursal",
    "Auditoria": "dbo.vw_AuditoriaCambioVendedor",
    "Presupuesto": "SQLite local: pto_sucursal | pto_vendedor | dbo.VwFacturaConImpuesto",
    "Reportes": "dbo.VwFacturaConImpuesto | dbo.VwExistencia | dbo.VwEntradasInventario | SQLite local: pto_linea_sucursal",
    "Mar-IA Agent": "Vistas oficiales de Wally | SQLite local de memoria",
    "Entrenamiento": "SQLite local: semantic_dictionary | training_entries",
    "Configuracion": "SQLite local | .env | vistas oficiales | dbo.VwColaboradoresTurno",
}


def render_header() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.sidebar.markdown(
        f"""
        <div class="wally-brand">
            <div class="wally-brand-mark">W</div>
            <div>
                <div class="wally-brand-title">{APP_NAME}</div>
                <div class="wally-brand-subtitle">Reportes, auditoria y Mar-IA</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        f"""
        <div class="wally-sidebar-status">
            <div><span>Base</span><strong>{env_value('SQL_DATABASE', 'WallyBD')}</strong></div>
            <div><span>Puerto</span><strong>{env_value('APP_PORT', '8504')}</strong></div>
            <div><span>Modo</span><strong>{env_value('APP_ENV', 'production')}</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("---")


def main() -> None:
    init_store()
    render_header()
    page_names = list(PAGES.keys())
    requested_page = st.query_params.get("page", page_names[0])
    if requested_page not in PAGES:
        requested_page = page_names[0]
    page_name = st.sidebar.radio(
        "Modulo",
        page_names,
        index=page_names.index(requested_page),
        key="active_page",
        label_visibility="collapsed",
    )
    if st.query_params.get("page") != page_name:
        st.query_params["page"] = page_name
    st.sidebar.markdown("---")
    st.sidebar.caption("Datos desde WallyBD Mirror")
    PAGES[page_name]()
    from services.ui import page_footer

    page_footer(PAGE_VIEWS[page_name])


if __name__ == "__main__":
    main()
