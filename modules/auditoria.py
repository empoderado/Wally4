from __future__ import annotations

import pandas as pd
import streamlit as st

from services import db
from services.catalog import get_code
from services.exports import dataframe_to_excel_bytes, export_filename
from services.formatting import money, number
from services.ui import code_footer, display_table, metric_card, page_title, section_title, warning_box


FLAG_COLUMNS = [
    "FlagCambioVendedor",
    "FlagCambioPosteriorPago",
    "FlagCambioPosteriorCierre",
    "FlagCambioTardio",
    "FlagPosibleNotaCredito",
]

BOOLEAN_DISPLAY_COLUMNS = [*FLAG_COLUMNS, "EsRiesgoFraude"]


def _where_clause(
    start_date,
    end_date,
    only_alerts: bool,
    branch: str,
    invoice: str,
    risk_levels: list[str] | None = None,
    alert_types: list[str] | None = None,
    fraud_only: bool = False,
) -> tuple[str, list[str]]:
    filters = ["CAST(Fecha AS date) BETWEEN ? AND ?"]
    params = [start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")]

    if only_alerts:
        filters.append(
            """
            (
                FlagCambioVendedor = 1
                OR FlagCambioPosteriorPago = 1
                OR FlagCambioPosteriorCierre = 1
                OR FlagCambioTardio = 1
                OR FlagPosibleNotaCredito = 1
            )
            """
        )
    if branch.strip():
        filters.append("CAST(idSucursal AS varchar(50)) = ?")
        params.append(branch.strip())
    if invoice.strip():
        filters.append("CAST(Numero AS varchar(80)) LIKE ?")
        params.append(f"%{invoice.strip()}%")
    if risk_levels:
        placeholders = ", ".join("?" for _ in risk_levels)
        filters.append(f"NivelRiesgo IN ({placeholders})")
        params.extend(risk_levels)
    if alert_types:
        filters.append("(" + " OR ".join("TipoAlerta LIKE ?" for _ in alert_types) + ")")
        params.extend(f"%{alert_type}%" for alert_type in alert_types)
    if fraud_only:
        filters.append("EsRiesgoFraude = 1")

    return " AND ".join(filters), params


def _load_summary(where_sql: str, params: list[str]) -> pd.DataFrame:
    return db.read_sql(
        f"""
        SELECT
            COUNT_BIG(*) AS Documentos,
            SUM(CASE WHEN FlagCambioVendedor = 1 THEN 1 ELSE 0 END) AS CambiosVendedor,
            SUM(CASE WHEN FlagCambioPosteriorPago = 1 THEN 1 ELSE 0 END) AS CambiosPosteriorPago,
            SUM(CASE WHEN FlagCambioPosteriorCierre = 1 THEN 1 ELSE 0 END) AS CambiosPosteriorCierre,
            SUM(CASE WHEN FlagCambioTardio = 1 THEN 1 ELSE 0 END) AS CambiosTardios,
            SUM(CASE WHEN FlagPosibleNotaCredito = 1 THEN 1 ELSE 0 END) AS PosiblesNotasCredito,
            SUM(CASE WHEN EsRiesgoFraude = 1 THEN 1 ELSE 0 END) AS RiesgoFraude,
            SUM(CASE WHEN NivelRiesgo = 'Alto' THEN 1 ELSE 0 END) AS RiesgoAlto,
            SUM(CASE WHEN NivelRiesgo = 'Medio' THEN 1 ELSE 0 END) AS RiesgoMedio,
            SUM(CASE WHEN NivelRiesgo = 'Bajo' THEN 1 ELSE 0 END) AS RiesgoBajo,
            SUM(CASE WHEN NivelRiesgo = 'Operativo' THEN 1 ELSE 0 END) AS Operativos,
            SUM(ISNULL(Total, 0)) AS MontoAuditado
        FROM {db.VIEW_AUDITORIA_CAMBIO_VENDEDOR}
        WHERE {where_sql}
        """,
        params,
    )


def _load_detail(where_sql: str, params: list[str], limit: int) -> pd.DataFrame:
    detail = db.read_sql(
        f"""
        SELECT TOP ({int(limit)})
            Sucursal,
            Numero,
            CONVERT(varchar(10), Fecha, 103) AS Fecha,
            NivelRiesgo,
            TipoAlerta,
            EsRiesgoFraude,
            NombreEmpleadoUsuario AS Empleado,
            NombreCaja AS Caja,
            Total,
            NombreVendedorInicial AS VendedorInicial,
            NombreVendedorFinal AS VendedorFinal,
            FlagCambioVendedor,
            CONVERT(varchar(10), FechaPrimerRegistro, 103) AS FechaPrimerRegistro,
            REPLACE(UsuarioPrimerRegistro, CHAR(0), '') AS UsuarioPrimerRegistro,
            CONVERT(varchar(10), FechaUltimoCambio, 103) AS FechaUltimoCambio,
            REPLACE(UsuarioUltimoCambio, CHAR(0), '') AS UsuarioUltimoCambio,
            CONVERT(varchar(10), FechaPrimerPago, 103) AS FechaPrimerPago,
            CONVERT(varchar(10), FechaUltimoPago, 103) AS FechaUltimoPago,
            CantidadPagos,
            FlagCambioPosteriorPago,
            CONVERT(varchar(10), FechaUltimoCierre, 103) AS FechaUltimoCierre,
            FlagCambioPosteriorCierre,
            CantidadEventosBIT,
            CantidadCambiosDetectados,
            MinutosHastaUltimoCambio,
            FlagCambioTardio,
            FlagPosibleNotaCredito,
            CONVERT(varchar(19), Fecha, 120) AS _FechaDocumentoHora,
            idTransaccionInv AS _idTransaccionInv,
            TransaccionInvDescripcion AS _TransaccionInvDescripcion,
            idMovimientoInvRef AS _idMovimientoInvRef,
            CONVERT(varchar(19), FechaPrimerRegistro, 120) AS _FechaPrimerRegistroHora,
            CONVERT(varchar(19), FechaUltimoCambio, 120) AS _FechaUltimoCambioHora,
            CONVERT(varchar(19), FechaPrimerPago, 120) AS _FechaPrimerPagoHora,
            CONVERT(varchar(19), FechaUltimoPago, 120) AS _FechaUltimoPagoHora,
            SegundosDespuesPago AS _SegundosDespuesPago,
            CONVERT(varchar(19), FechaUltimoCierre, 120) AS _FechaUltimoCierreHora
        FROM {db.VIEW_AUDITORIA_CAMBIO_VENDEDOR}
        WHERE {where_sql}
        ORDER BY
            FlagCambioPosteriorCierre DESC,
            FlagCambioPosteriorPago DESC,
            FlagCambioVendedor DESC,
            FechaUltimoCambio DESC
        """,
        params,
    )
    detail = _clean_audit_text(detail)
    return _add_audit_comments(detail)


def _clean_audit_text(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return data
    cleaned = data.copy()
    for column in ("UsuarioPrimerRegistro", "UsuarioUltimoCambio"):
        if column in cleaned.columns:
            cleaned[column] = (
                cleaned[column]
                .fillna("")
                .astype(str)
                .str.replace("\x00", "", regex=False)
                .str.strip()
            )
    return cleaned


def _is_true(value) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "si", "sí", "yes"}
    return bool(value)


def _value_or_empty(value) -> str:
    if pd.isna(value) or value is None:
        return ""
    text = str(value).replace("\x00", "").strip()
    if text.lower() in {"nan", "none", "nat"}:
        return ""
    return text


def _value_or_label(value, label: str = "sin dato") -> str:
    return _value_or_empty(value) or label


def _flag_names(row: pd.Series) -> list[str]:
    flags = []
    if _is_true(row.get("FlagCambioVendedor")):
        flags.append("FlagCambioVendedor")
    if _is_true(row.get("FlagCambioPosteriorPago")):
        flags.append("FlagCambioPosteriorPago")
    if _is_true(row.get("FlagCambioPosteriorCierre")):
        flags.append("FlagCambioPosteriorCierre")
    if _is_true(row.get("FlagCambioTardio")):
        flags.append("FlagCambioTardio")
    if _is_true(row.get("FlagPosibleNotaCredito")):
        flags.append("FlagPosibleNotaCredito")
    return flags


def _audit_comment(row: pd.Series) -> str:
    numero = _value_or_label(row.get("Numero"))
    sucursal = _value_or_label(row.get("Sucursal"))
    fecha = _value_or_label(row.get("Fecha"))
    fecha_hora = _value_or_label(row.get("_FechaDocumentoHora"))
    transaccion_id = _value_or_label(row.get("_idTransaccionInv"))
    transaccion = _value_or_label(row.get("_TransaccionInvDescripcion"))
    nivel = _value_or_label(row.get("NivelRiesgo"))
    tipo_alerta = _value_or_label(row.get("TipoAlerta"))
    riesgo_fraude = "SI" if _is_true(row.get("EsRiesgoFraude")) else "No"
    referencia = _value_or_label(row.get("_idMovimientoInvRef"))
    vendedor_inicial = _value_or_label(row.get("VendedorInicial"))
    vendedor_final = _value_or_label(row.get("VendedorFinal"))
    usuario_primer = _value_or_label(row.get("UsuarioPrimerRegistro"))
    usuario_ultimo = _value_or_label(row.get("UsuarioUltimoCambio"))
    fecha_primer_registro = _value_or_label(row.get("_FechaPrimerRegistroHora"))
    fecha_ultimo_cambio = _value_or_label(row.get("_FechaUltimoCambioHora"))
    fecha_primer_pago = _value_or_label(row.get("_FechaPrimerPagoHora"))
    fecha_ultimo_pago = _value_or_label(row.get("_FechaUltimoPagoHora"))
    fecha_ultimo_cierre = _value_or_label(row.get("_FechaUltimoCierreHora"))
    flags = _flag_names(row)

    lines = [
        f"El documento {numero} aparece en T-AUD-01 Detalle de alertas con fecha documento {fecha} por la(s) bandera(s): {', '.join(flags) if flags else 'sin banderas activas'}.",
        "",
        "Resultado real consultado en WallyBD:",
        f"- Numero: {numero}",
        f"- Sucursal: {sucursal}",
        f"- Fecha documento: {fecha}",
        f"- Fecha documento hora: {fecha_hora}",
        f"- Nivel de riesgo: {nivel}",
        f"- Tipo de alerta: {tipo_alerta}",
        f"- Es riesgo fraude: {riesgo_fraude}",
        f"- Transaccion: idTransaccionInv = {transaccion_id}, {transaccion}",
        f"- Documento referencia: {referencia}",
        f"- Vendedor inicial: {vendedor_inicial}",
        f"- Vendedor final: {vendedor_final}",
        f"- Usuario primer registro: {usuario_primer}",
        f"- Usuario ultimo cambio: {usuario_ultimo}",
        f"- Fecha primer registro: {fecha_primer_registro}",
        f"- Fecha ultimo cambio: {fecha_ultimo_cambio}",
        f"- Fecha primer pago: {fecha_primer_pago}",
        f"- Fecha ultimo pago: {fecha_ultimo_pago}",
        f"- Fecha ultimo cierre: {fecha_ultimo_cierre}",
        "",
        "Justificacion:",
    ]

    if _is_true(row.get("FlagCambioVendedor")):
        lines.append(
            f"- Aparece por cambio de vendedor: el vendedor inicial ({vendedor_inicial}) es diferente al vendedor final ({vendedor_final}), por eso FlagCambioVendedor = SI."
        )
    if _is_true(row.get("FlagCambioPosteriorPago")):
        seconds = _value_or_label(row.get("_SegundosDespuesPago"))
        lines.append(
            f"- Aparece por cambio posterior al pago: FechaUltimoCambio {fecha_ultimo_cambio} ocurre despues de FechaUltimoPago {fecha_ultimo_pago} por {seconds} segundos, superando la tolerancia de 60 segundos; por eso FlagCambioPosteriorPago = SI."
        )
    if _is_true(row.get("FlagCambioPosteriorCierre")):
        lines.append(
            f"- Aparece por cambio posterior al cierre: FechaUltimoCambio {fecha_ultimo_cambio} es posterior a FechaUltimoCierre {fecha_ultimo_cierre}, por eso FlagCambioPosteriorCierre = SI."
        )
    if _is_true(row.get("FlagCambioTardio")):
        minutes = _value_or_label(row.get("MinutosHastaUltimoCambio"))
        lines.append(
            f"- Aparece por cambio tardio: entre FechaPrimerRegistro {fecha_primer_registro} y FechaUltimoCambio {fecha_ultimo_cambio} pasaron {minutes} minutos, superando 60 minutos; por eso FlagCambioTardio = SI."
        )
    if _is_true(row.get("FlagPosibleNotaCredito")):
        lines.append(
            f"- Aparece por posible nota credito: la transaccion es idTransaccionInv = {transaccion_id}, {transaccion}; por eso FlagPosibleNotaCredito = SI."
        )
    if not flags:
        lines.append("- No tiene banderas de alerta activas; aparece porque los filtros actuales permiten ver documentos sin alerta.")

    if str(transaccion_id) in {"4", "5"}:
        lines.extend(
            [
                "",
                "Interpretacion:",
                f"- Es un traslado entre sucursales registrado como {transaccion}. Tecnicamente la regla lo puede detectar si coincide con una bandera activa; funcionalmente puede ser una operacion normal de traslado y debe revisarse como excepcion operativa.",
            ]
        )

    return "\n".join(lines)


def _add_audit_comments(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return data
    commented = data.copy()
    commented["Comentario"] = commented.apply(_audit_comment, axis=1)
    helper_columns = [column for column in commented.columns if column.startswith("_")]
    return _format_boolean_display(commented.drop(columns=helper_columns))


def _format_boolean_display(data: pd.DataFrame) -> pd.DataFrame:
    formatted = data.copy()
    for column in BOOLEAN_DISPLAY_COLUMNS:
        if column in formatted.columns:
            formatted[column] = formatted[column].map(lambda value: "SI" if _is_true(value) else "No")
    return formatted


def _highlight_audit_row(row: pd.Series) -> list[str]:
    is_fraud = str(row.get("EsRiesgoFraude", "")).strip().upper() == "SI" or "Es riesgo fraude: SI" in str(row.get("Comentario", ""))
    if is_fraud:
        return ["background-color: #fee2e2; color: #991b1b; font-weight: 700;" for _ in row]
    return ["" for _ in row]


def _highlight_high_risk(value: object) -> str:
    if str(value).strip().lower() == "alto":
        return "color: #b91c1c; font-weight: 800;"
    return ""


def _display_audit_detail_table(data: pd.DataFrame) -> None:
    numeric_columns = [column for column in data.columns if pd.api.types.is_numeric_dtype(data[column])]
    styler = data.style.apply(_highlight_audit_row, axis=1)
    if "NivelRiesgo" in data.columns:
        styler = styler.applymap(_highlight_high_risk, subset=["NivelRiesgo"])
    if numeric_columns:
        styler = styler.set_properties(subset=numeric_columns, **{"text-align": "right"})
    st.dataframe(styler, use_container_width=True, hide_index=True, height=470)


def _load_by_user(where_sql: str, params: list[str]) -> pd.DataFrame:
    return db.read_sql(
        f"""
        SELECT TOP (25)
            UsuarioUltimoCambio,
            COUNT_BIG(*) AS Documentos,
            SUM(CASE WHEN FlagCambioVendedor = 1 THEN 1 ELSE 0 END) AS CambiosVendedor,
            SUM(CASE WHEN FlagCambioPosteriorPago = 1 THEN 1 ELSE 0 END) AS CambiosPosteriorPago,
            SUM(CASE WHEN FlagCambioPosteriorCierre = 1 THEN 1 ELSE 0 END) AS CambiosPosteriorCierre,
            SUM(ISNULL(Total, 0)) AS MontoAuditado
        FROM {db.VIEW_AUDITORIA_CAMBIO_VENDEDOR}
        WHERE {where_sql}
          AND UsuarioUltimoCambio IS NOT NULL
        GROUP BY UsuarioUltimoCambio
        ORDER BY CambiosPosteriorCierre DESC, CambiosPosteriorPago DESC, CambiosVendedor DESC, Documentos DESC
        """,
        params,
    )


def render() -> None:
    page_title("Auditoria", "Cambio de vendedor, modificaciones posteriores y notas credito")

    min_date, max_date = db.min_max_date()
    st.sidebar.markdown("### Filtros auditoria")
    start_date = st.sidebar.date_input("Desde", value=max_date, min_value=min_date, max_value=max_date, key="auditoria_desde")
    end_date = st.sidebar.date_input("Hasta", value=max_date, min_value=min_date, max_value=max_date, key="auditoria_hasta")
    only_alerts = st.sidebar.checkbox("Solo alertas", value=True)
    risk_levels = st.sidebar.multiselect(
        "Nivel de riesgo",
        ["Alto", "Medio", "Bajo", "Operativo"],
        default=["Alto", "Medio", "Bajo"],
    )
    alert_types = st.sidebar.multiselect(
        "Tipo de alerta",
        [
            "Cambio de vendedor",
            "Cambio posterior al pago",
            "Cambio posterior al cierre",
            "Cambio tardio",
            "Nota de credito",
            "Traslado operativo",
        ],
    )
    fraud_only = st.sidebar.checkbox("Solo riesgo fraude", value=False)
    branch = st.sidebar.text_input("idSucursal")
    invoice = st.sidebar.text_input("Numero factura")
    limit = st.sidebar.slider("Registros detalle", min_value=50, max_value=1000, value=250, step=50)

    if start_date > end_date:
        warning_box("La fecha inicial no puede ser mayor que la fecha final.")
        return

    where_sql, params = _where_clause(
        start_date,
        end_date,
        only_alerts,
        branch,
        invoice,
        risk_levels,
        alert_types,
        fraud_only,
    )

    try:
        summary = _load_summary(where_sql, params)
        detail = _load_detail(where_sql, params, limit)
        by_user = _load_by_user(where_sql, params)
    except Exception as exc:
        st.error("No se pudo cargar la auditoria. Verifica que WallyBD y dbo.vw_AuditoriaCambioVendedor existan.")
        st.exception(exc)
        return

    if summary.empty:
        warning_box("No hay datos de auditoria para el periodo seleccionado.")
        return

    row = summary.iloc[0].fillna(0)
    cols = st.columns(8)
    with cols[0]:
        metric_card("Documentos", number(row["Documentos"]))
    with cols[1]:
        metric_card("Riesgo fraude", number(row["RiesgoFraude"]))
    with cols[2]:
        metric_card("Alto", number(row["RiesgoAlto"]))
    with cols[3]:
        metric_card("Medio", number(row["RiesgoMedio"]))
    with cols[4]:
        metric_card("Bajo", number(row["RiesgoBajo"]))
    with cols[5]:
        metric_card("Operativo", number(row["Operativos"]))
    with cols[6]:
        metric_card("Cambio vendedor", number(row["CambiosVendedor"]))
    with cols[7]:
        metric_card("Monto auditado", money(row["MontoAuditado"]))
    code_footer(*get_code("auditoria", "report"))

    section_title("Detalle de alertas")
    if detail.empty:
        warning_box("No hay alertas con los filtros actuales.")
    else:
        _display_audit_detail_table(detail)
        code_footer(*get_code("auditoria", "detail_table"))

    section_title("Usuarios con modificaciones")
    display_table(by_user, height=330, show_total=False)
    code_footer(*get_code("auditoria", "users_table"))

    st.download_button(
        "Exportar auditoria a Excel",
        dataframe_to_excel_bytes({"Resumen": summary, "Detalle": detail, "Usuarios": by_user}),
        file_name=export_filename("wally_auditoria_cambio_vendedor"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
