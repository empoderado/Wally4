from __future__ import annotations

import streamlit as st

from services import db
from services.formatting import money, number
from services.ui import page_title, section_title


def render() -> None:
    page_title("WallyAgent", "Base paralela para Mar-IA Agent")
    ok, message = db.test_connection()
    if ok:
        st.success(message)
    else:
        st.warning(message)

    section_title("Estado inicial")
    st.write("Esta app corre independiente de Wally y usa las vistas autorizadas de `WallyBD`.")
    st.write("El ERP StudioF no se consulta directamente desde la app.")
    if db.use_mock_data():
        st.info("Modo desarrollo: los indicadores usan datos simulados. En el servidor se cambia `USE_MOCK_DATA=no` para consultar SQL Server real.")

    if st.button("Probar KPI ventas hoy"):
        try:
            df = db.read_sql(
                f"""
                SELECT
                    SUM(ISNULL(VentaNetaQ, 0)) AS VentaNetaQ,
                    SUM(ISNULL(Unidades, 0)) AS Unidades,
                    COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END) AS Facturas
                FROM {db.VIEW_VENTAS}
                WHERE CAST(Fecha AS date) = CAST(GETDATE() AS date)
                """
            )
            row = df.iloc[0]
            c1, c2, c3 = st.columns(3)
            c1.metric("Venta Neta Q", money(row["VentaNetaQ"]))
            c2.metric("Unidades", number(row["Unidades"]))
            c3.metric("Facturas", number(row["Facturas"]))
        except Exception as exc:
            st.error("No se pudo consultar el KPI. En local activa USE_MOCK_DATA=yes o prueba en el servidor.")
            st.caption(str(exc))
