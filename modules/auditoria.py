from __future__ import annotations

import pandas as pd
import streamlit as st
from datetime import timedelta

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

DOCUMENT_KEY_SQL = "CONCAT(CAST(idSucursal AS varchar(20)), '|', CAST(idMovimientoInv AS varchar(30)))"


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
    filters = ["Fecha >= ? AND Fecha < DATEADD(day, 1, ?)"]
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
            COUNT(DISTINCT CASE WHEN FlagCambioVendedor = 1 THEN {DOCUMENT_KEY_SQL} END) AS CambiosVendedor,
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
            VendedorInicial AS CodigoVendedorInicial,
            NombreVendedorInicial AS VendedorInicial,
            COALESCE(IdVendedorFactura, VendedorFinalBIT) AS CodigoVendedorFinal,
            NombreVendedorFinal AS VendedorFinal,
            IdVendedorFactura AS CodigoVendedorFactura,
            VendedorFinalBIT AS CodigoVendedorFinalBIT,
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
            cleaned[column] = _clean_user_series(cleaned[column])
    return cleaned


def _clean_user_series(series: pd.Series) -> pd.Series:
    return (
        series.fillna("")
        .astype(str)
        .str.replace(r"[\x00-\x1f\x7f-\x9f]", "", regex=True)
        .str.replace("\ufffd", "", regex=False)
        .str.replace(r"[^\w\s.@-]", "", regex=True)
        .str.strip()
    )


def _group_by_clean_user(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty or "UsuarioUltimoCambio" not in data.columns:
        return data
    cleaned = data.copy()
    cleaned["UsuarioUltimoCambio"] = _clean_user_series(cleaned["UsuarioUltimoCambio"])
    cleaned = cleaned[cleaned["UsuarioUltimoCambio"] != ""]
    if cleaned.empty:
        return cleaned
    aggregations = {
        column: "sum"
        for column in cleaned.columns
        if column != "UsuarioUltimoCambio" and pd.api.types.is_numeric_dtype(cleaned[column])
    }
    if "UltimoCambio" in cleaned.columns:
        aggregations["UltimoCambio"] = "max"
    grouped = cleaned.groupby("UsuarioUltimoCambio", as_index=False).agg(aggregations)
    sort_columns = [
        column
        for column in ("RiesgoFraude", "CambiosPosteriorPago", "CambiosPosteriorCierre", "CambiosVendedor", "Documentos")
        if column in grouped.columns
    ]
    if sort_columns:
        grouped = grouped.sort_values(sort_columns, ascending=[False] * len(sort_columns))
    return grouped.reset_index(drop=True)


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


def _classify_late_change(row: pd.Series) -> str:
    if not _is_true(row.get("FlagCambioTardio")):
        return ""
    types: list[str] = []
    if _is_true(row.get("FlagCambioVendedor")):
        types.append("Cambio (vendedor)")
    if _is_true(row.get("FlagCambioPosteriorPago")):
        types.append("Cambio (Metodo pago)")
    if _is_true(row.get("FlagCambioPosteriorCierre")):
        types.append("Cambio (posterior al cierre)")
    if _is_true(row.get("FlagPosibleNotaCredito")):
        types.append("Cambio (NC)")
    total_first = _value_or_empty(row.get("TotalPrimerRegistro"))
    total_last = _value_or_empty(row.get("TotalUltimoRegistro"))
    if total_first and total_last and total_first != total_last:
        types.append("Cambio (valor monto total)")
    if not types:
        types.append("Cambio (tardio sin diferencia visible)")
    return "; ".join(types)


def _audit_comment(row: pd.Series) -> str:
    numero = _value_or_label(row.get("Numero"))
    sucursal = _value_or_label(row.get("Sucursal"))
    fecha = _value_or_label(row.get("Fecha"))
    fecha_hora = _value_or_label(row.get("_FechaDocumentoHora"))
    transaccion_id = _value_or_label(row.get("_idTransaccionInv"))
    transaccion = _value_or_label(row.get("_TransaccionInvDescripcion"))
    nivel = _value_or_label(row.get("NivelRiesgo"))
    tipo_alerta = _plain_alert_type(_value_or_label(row.get("TipoAlerta")))
    tipo_cambio_tardio = _value_or_empty(row.get("TipoCambioTardio"))
    riesgo_fraude = "SI" if _is_true(row.get("EsRiesgoFraude")) else "No"
    referencia = _value_or_label(row.get("_idMovimientoInvRef"))
    vendedor_inicial = _value_or_label(row.get("VendedorInicial"))
    vendedor_final = _value_or_label(row.get("VendedorFinal"))
    codigo_vendedor_inicial = _value_or_label(row.get("CodigoVendedorInicial"))
    codigo_vendedor_final = _value_or_label(row.get("CodigoVendedorFinal"))
    codigo_vendedor_factura = _value_or_empty(row.get("CodigoVendedorFactura"))
    codigo_vendedor_bit = _value_or_label(row.get("CodigoVendedorFinalBIT"))
    usuario_primer = _value_or_label(row.get("UsuarioPrimerRegistro"))
    usuario_ultimo = _value_or_label(row.get("UsuarioUltimoCambio"))
    fecha_primer_registro = _value_or_label(row.get("_FechaPrimerRegistroHora"))
    fecha_ultimo_cambio = _value_or_label(row.get("_FechaUltimoCambioHora"))
    fecha_primer_pago = _value_or_label(row.get("_FechaPrimerPagoHora"))
    fecha_ultimo_pago = _value_or_label(row.get("_FechaUltimoPagoHora"))
    fecha_ultimo_cierre = _value_or_label(row.get("_FechaUltimoCierreHora"))
    tipo_cambio_tardio = _value_or_empty(row.get("TipoCambioTardio"))
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
        f"- Vendedor inicial: {codigo_vendedor_inicial} - {vendedor_inicial}",
        f"- Vendedor final auditado: {codigo_vendedor_final} - {vendedor_final}",
        f"- Vendedor final BIT: {codigo_vendedor_bit}",
        f"- Usuario primer registro: {usuario_primer}",
        f"- Usuario que hizo la modificacion auditada: {usuario_ultimo}",
        f"- Fecha primer registro: {fecha_primer_registro}",
        f"- Fecha de la modificacion auditada: {fecha_ultimo_cambio}",
        f"- Fecha primer pago: {fecha_primer_pago}",
        f"- Fecha ultimo pago: {fecha_ultimo_pago}",
        f"- Fecha ultimo cierre: {fecha_ultimo_cierre}",
        "",
        "Justificacion:",
    ]

    if _is_true(row.get("FlagCambioVendedor")):
        source = "VwFacturaConImpuesto.IdVendedor" if codigo_vendedor_factura else "BITMovimientoInv final"
        lines.append(
            f"- Aparece por cambio (vendedor): el vendedor inicial ({codigo_vendedor_inicial} - {vendedor_inicial}) es diferente al vendedor final auditado ({codigo_vendedor_final} - {vendedor_final}) tomado de {source}; por eso FlagCambioVendedor = SI."
        )
    if _is_true(row.get("FlagCambioPosteriorPago")):
        seconds = _value_or_label(row.get("_SegundosDespuesPago"))
        lines.append(
            f"- Aparece por cambio (Metodo pago): FechaUltimoCambio {fecha_ultimo_cambio} ocurre despues de FechaUltimoPago {fecha_ultimo_pago} por {seconds} segundos, superando la tolerancia de 60 segundos; por eso FlagCambioPosteriorPago = SI."
        )
    if _is_true(row.get("FlagCambioPosteriorCierre")):
        lines.append(
            f"- Aparece por cambio (posterior al cierre): FechaUltimoCambio {fecha_ultimo_cambio} es posterior a FechaUltimoCierre {fecha_ultimo_cierre}, por eso FlagCambioPosteriorCierre = SI."
        )
    if _is_true(row.get("FlagCambioTardio")):
        minutes = _value_or_label(row.get("MinutosHastaUltimoCambio"))
        lines.append(
            f"- Aparece por cambio (tardio): entre FechaPrimerRegistro {fecha_primer_registro} y FechaUltimoCambio {fecha_ultimo_cambio} pasaron {minutes} minutos, superando 60 minutos. Tipo de cambio tardio: {tipo_cambio_tardio or 'Cambio (tardio sin diferencia visible)'}. Por eso FlagCambioTardio = SI."
        )
    if _is_true(row.get("FlagPosibleNotaCredito")):
        lines.append(
            f"- Aparece por cambio (NC): la transaccion es idTransaccionInv = {transaccion_id}, {transaccion}; por eso FlagPosibleNotaCredito = SI."
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
    commented["TipoCambioTardio"] = commented.apply(_classify_late_change, axis=1)
    if "TipoAlerta" in commented.columns:
        commented["TipoAlerta"] = commented.apply(_append_late_change_type_to_alert, axis=1)
    commented["Comentario"] = commented.apply(_audit_comment, axis=1)
    helper_columns = [column for column in commented.columns if column.startswith("_")]
    return _format_boolean_display(commented.drop(columns=helper_columns))


def _append_late_change_type_to_alert(row: pd.Series) -> str:
    alert = _value_or_label(row.get("TipoAlerta"), "Sin alerta")
    late_type = _value_or_empty(row.get("TipoCambioTardio"))
    if late_type and late_type not in alert:
        return f"{alert}; {late_type}"
    return alert


def _plain_alert_explanation(row: pd.Series) -> dict[str, str]:
    numero = _value_or_label(row.get("Numero"))
    sucursal = _value_or_label(row.get("Sucursal"))
    fecha = _value_or_label(row.get("Fecha"))
    nivel = _value_or_label(row.get("NivelRiesgo"))
    tipo_alerta = _plain_alert_type(_value_or_label(row.get("TipoAlerta")))
    total = _value_or_label(row.get("Total"))
    usuario = _value_or_label(row.get("UsuarioUltimoCambio"))
    vendedor_inicial = _value_or_label(row.get("VendedorInicial"))
    vendedor_final = _value_or_label(row.get("VendedorFinal"))
    fecha_ultimo_cambio = _value_or_label(row.get("FechaUltimoCambio"))
    fecha_ultimo_pago = _value_or_label(row.get("FechaUltimoPago"))
    fecha_ultimo_cierre = _value_or_label(row.get("FechaUltimoCierre"))
    tipo_cambio_tardio = _value_or_empty(row.get("TipoCambioTardio"))

    facts: list[str] = []
    reasons: list[str] = []
    review: list[str] = []
    fraud_signals: list[str] = []

    if _is_true(row.get("FlagCambioVendedor")):
        facts.append(f"El documento tuvo cambio (vendedor): paso de {vendedor_inicial} a {vendedor_final}.")
        reasons.append("Puede afectar comisiones, responsabilidad de la venta y trazabilidad del documento.")
        review.append("Confirmar quien autorizo el cambio (vendedor) y si corresponde al asesor que hizo la venta.")
        fraud_signals.append("Cambio (vendedor)")

    if _is_true(row.get("FlagCambioPosteriorPago")):
        facts.append(f"El documento tuvo cambio (Metodo pago) despues de registrar el pago. Ultimo pago: {fecha_ultimo_pago}; ultimo cambio (Metodo pago): {fecha_ultimo_cambio}.")
        reasons.append("Cuando una factura tiene cambio (Metodo pago) despues de pagada, puede alterar datos ya cerrados con el cliente o caja.")
        review.append("Comparar la factura contra el recibo/pago y validar si el cambio (Metodo pago) tenia autorizacion.")
        fraud_signals.append("Cambio (Metodo pago)")

    if _is_true(row.get("FlagCambioPosteriorCierre")):
        facts.append(f"El documento tuvo cambio (posterior al cierre). Cierre: {fecha_ultimo_cierre}; ultimo cambio (posterior al cierre): {fecha_ultimo_cambio}.")
        reasons.append("Un cambio (posterior al cierre) ocurre fuera del flujo normal de caja y debe justificarse.")
        review.append("Revisar el soporte del cierre, el usuario que hizo el cambio (posterior al cierre) y si el ajuste fue autorizado.")
        fraud_signals.append("Cambio (posterior al cierre)")

    if _is_true(row.get("FlagCambioTardio")):
        minutes = _value_or_label(row.get("MinutosHastaUltimoCambio"))
        facts.append(f"El documento tuvo cambio (tardio), aproximadamente {minutes} minutos despues del primer registro. Tipo de cambio tardio: {tipo_cambio_tardio or 'Cambio (tardio sin diferencia visible)'}.")
        reasons.append("Un cambio (tardio) puede indicar correccion manual o ajuste no habitual; el tipo ayuda a entender que se debe revisar.")
        review.append("Validar la razon del cambio (tardio) y revisar si coincide con una solicitud del cliente o de la tienda.")

    if _is_true(row.get("FlagPosibleNotaCredito")):
        facts.append("El documento tuvo cambio (NC): corresponde a una nota de credito o reversa de venta.")
        reasons.append("El cambio (NC) reduce o reversa ventas; si no esta soportado puede ocultar errores o devoluciones indebidas.")
        review.append("Verificar autorizacion, motivo del cambio (NC), producto devuelto y documento original.")
        if str(row.get("EsRiesgoFraude", "")).strip().upper() == "SI":
            fraud_signals.append("Cambio (NC)")

    if not facts:
        facts.append("El documento no tiene una bandera critica activa con los filtros actuales.")
        reasons.append("Se muestra por los filtros seleccionados, pero no requiere revision prioritaria por fraude.")
        review.append("Revisar solo si el documento hace parte de otra investigacion.")

    possible_fraud = "SI" if str(row.get("EsRiesgoFraude", "")).strip().upper() == "SI" else "No"
    if possible_fraud == "SI" and not fraud_signals:
        fraud_signals.append("La combinacion de alertas eleva el riesgo")

    return {
        "Documento": numero,
        "Sucursal": sucursal,
        "Fecha": fecha,
        "Nivel de riesgo": nivel,
        "Posible fraude": possible_fraud,
        "Tipo de alerta": tipo_alerta,
        "Tipo de cambio tardio": tipo_cambio_tardio,
        "Que paso": " ".join(facts),
        "Por que importa": " ".join(dict.fromkeys(reasons)),
        "Que revisar": " ".join(dict.fromkeys(review)),
        "Senales de riesgo": ", ".join(fraud_signals) if fraud_signals else "Sin senal fuerte de fraude",
        "Usuario que hizo la modificacion": usuario,
        "Monto total": total,
    }


def _plain_alert_type(tipo_alerta: str) -> str:
    replacements = {
        "Cambio de vendedor": "Cambio (vendedor)",
        "Cambio posterior al pago": "Cambio (Metodo pago)",
        "Cambio posterior al cierre": "Cambio (posterior al cierre)",
        "Cambio tardio": "Cambio (tardio)",
        "Nota de credito": "Cambio (NC)",
    }
    text = tipo_alerta
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _build_plain_language_export(detail: pd.DataFrame) -> pd.DataFrame:
    if detail.empty:
        return pd.DataFrame(
            columns=[
                "Documento",
                "Sucursal",
                "Fecha",
                "Nivel de riesgo",
                "Posible fraude",
                "Tipo de alerta",
                "Tipo de cambio tardio",
                "Que paso",
                "Por que importa",
                "Que revisar",
                "Senales de riesgo",
                "Usuario que hizo la modificacion",
                "Monto total",
            ]
        )
    return pd.DataFrame([_plain_alert_explanation(row) for _, row in detail.iterrows()])


def _build_detail_export(detail: pd.DataFrame) -> pd.DataFrame:
    if detail.empty:
        return detail
    export_detail = detail.copy()
    if "TipoAlerta" in export_detail.columns:
        export_detail["TipoAlerta"] = export_detail["TipoAlerta"].map(lambda value: _plain_alert_type(_value_or_label(value)))
    return export_detail


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
    users = db.read_sql(
        f"""
        SELECT
            UsuarioUltimoCambio,
            COUNT_BIG(*) AS Documentos,
            SUM(CASE WHEN EsRiesgoFraude = 1 THEN 1 ELSE 0 END) AS RiesgoFraude,
            COUNT(DISTINCT CASE WHEN FlagCambioVendedor = 1 THEN {DOCUMENT_KEY_SQL} END) AS CambiosVendedor,
            SUM(CASE WHEN FlagCambioPosteriorPago = 1 THEN 1 ELSE 0 END) AS CambiosPosteriorPago,
            SUM(CASE WHEN FlagCambioPosteriorCierre = 1 THEN 1 ELSE 0 END) AS CambiosPosteriorCierre,
            SUM(CASE WHEN FlagCambioTardio = 1 THEN 1 ELSE 0 END) AS CambiosTardios,
            SUM(CASE WHEN FlagPosibleNotaCredito = 1 THEN 1 ELSE 0 END) AS NotasCredito,
            SUM(ISNULL(Total, 0)) AS MontoAuditado
        FROM {db.VIEW_AUDITORIA_CAMBIO_VENDEDOR}
        WHERE {where_sql}
          AND UsuarioUltimoCambio IS NOT NULL
        GROUP BY UsuarioUltimoCambio
        ORDER BY RiesgoFraude DESC, CambiosPosteriorPago DESC, CambiosPosteriorCierre DESC, CambiosVendedor DESC, Documentos DESC
        """,
        params,
    )
    return _group_by_clean_user(users)


def _load_by_branch(where_sql: str, params: list[str]) -> pd.DataFrame:
    return db.read_sql(
        f"""
        SELECT TOP (25)
            Sucursal,
            COUNT_BIG(*) AS Documentos,
            SUM(CASE WHEN EsRiesgoFraude = 1 THEN 1 ELSE 0 END) AS RiesgoFraude,
            SUM(CASE WHEN NivelRiesgo = 'Alto' THEN 1 ELSE 0 END) AS RiesgoAlto,
            SUM(CASE WHEN NivelRiesgo = 'Medio' THEN 1 ELSE 0 END) AS RiesgoMedio,
            SUM(CASE WHEN NivelRiesgo = 'Bajo' THEN 1 ELSE 0 END) AS RiesgoBajo,
            COUNT(DISTINCT CASE WHEN FlagCambioVendedor = 1 THEN {DOCUMENT_KEY_SQL} END) AS CambiosVendedor,
            SUM(CASE WHEN FlagCambioPosteriorPago = 1 THEN 1 ELSE 0 END) AS CambiosPosteriorPago,
            SUM(CASE WHEN FlagCambioPosteriorCierre = 1 THEN 1 ELSE 0 END) AS CambiosPosteriorCierre,
            SUM(CASE WHEN FlagPosibleNotaCredito = 1 THEN 1 ELSE 0 END) AS NotasCredito,
            SUM(ISNULL(Total, 0)) AS MontoAuditado
        FROM {db.VIEW_AUDITORIA_CAMBIO_VENDEDOR}
        WHERE {where_sql}
        GROUP BY Sucursal
        ORDER BY RiesgoFraude DESC, RiesgoAlto DESC, RiesgoMedio DESC, Documentos DESC
        """,
        params,
    )


def _load_change_vendor_users(where_sql: str, params: list[str]) -> pd.DataFrame:
    users = db.read_sql(
        f"""
        SELECT
            UsuarioUltimoCambio,
            COUNT(DISTINCT {DOCUMENT_KEY_SQL}) AS CambiosVendedor,
            COUNT(DISTINCT {DOCUMENT_KEY_SQL}) AS Documentos,
            COUNT(DISTINCT Sucursal) AS Sucursales,
            SUM(ISNULL(Total, 0)) AS MontoAuditado,
            MAX(CONVERT(varchar(19), FechaUltimoCambio, 120)) AS UltimoCambio
        FROM {db.VIEW_AUDITORIA_CAMBIO_VENDEDOR}
        WHERE {where_sql}
          AND FlagCambioVendedor = 1
          AND UsuarioUltimoCambio IS NOT NULL
        GROUP BY UsuarioUltimoCambio
        ORDER BY CambiosVendedor DESC, MontoAuditado DESC
        """,
        params,
    )
    return _group_by_clean_user(users)


def _load_change_vendor_documents(where_sql: str, params: list[str]) -> pd.DataFrame:
    documents = db.read_sql(
        f"""
        SELECT
            CONVERT(varchar(10), Fecha, 103) AS Fecha,
            Sucursal,
            Numero,
            VendedorInicial AS CodigoVendedorInicial,
            NombreVendedorInicial AS VendedorInicial,
            COALESCE(IdVendedorFactura, VendedorFinalBIT) AS CodigoVendedorFinal,
            NombreVendedorFinal AS VendedorFinal,
            IdVendedorFactura AS CodigoVendedorFactura,
            VendedorFinalBIT AS CodigoVendedorFinalBIT,
            Total,
            REPLACE(UsuarioPrimerRegistro, CHAR(0), '') AS UsuarioPrimerRegistro,
            REPLACE(UsuarioUltimoCambio, CHAR(0), '') AS UsuarioUltimoCambio,
            CONVERT(varchar(19), FechaPrimerRegistro, 120) AS FechaPrimerRegistro,
            CONVERT(varchar(19), FechaUltimoCambio, 120) AS FechaUltimoCambio,
            CantidadCambiosDetectados,
            NivelRiesgo,
            TipoAlerta
        FROM {db.VIEW_AUDITORIA_CAMBIO_VENDEDOR}
        WHERE {where_sql}
          AND FlagCambioVendedor = 1
        ORDER BY Fecha DESC, Numero
        """,
        params,
    )
    documents = _clean_audit_text(documents)
    if not documents.empty:
        documents["TipoCambioTardio"] = documents.apply(_classify_late_change, axis=1)
    return documents


def _load_change_vendor_diagnostics(start_date, end_date) -> pd.DataFrame:
    return db.read_sql(
        f"""
        SELECT
            COUNT_BIG(*) AS DiferenciasVendedor,
            SUM(CASE WHEN idTransaccionInv = 31 THEN 1 ELSE 0 END) AS DiferenciasEnPedidos,
            SUM(CASE WHEN idTransaccionInv <> 31 THEN 1 ELSE 0 END) AS DiferenciasAuditables,
            MIN(CAST(Fecha AS date)) AS PrimeraFecha,
            MAX(CAST(Fecha AS date)) AS UltimaFecha
        FROM {db.VIEW_AUDITORIA_CAMBIO_VENDEDOR}
        WHERE Fecha >= ? AND Fecha < DATEADD(day, 1, ?)
          AND VendedorInicial IS NOT NULL
          AND COALESCE(IdVendedorFactura, VendedorFinalBIT) IS NOT NULL
          AND ISNULL(VendedorInicial, -1) <> ISNULL(COALESCE(IdVendedorFactura, VendedorFinalBIT), -1)
        """,
        [start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")],
    )


def _load_risk_mix(where_sql: str, params: list[str]) -> pd.DataFrame:
    return db.read_sql(
        f"""
        SELECT
            NivelRiesgo,
            COUNT_BIG(*) AS Documentos,
            SUM(CASE WHEN EsRiesgoFraude = 1 THEN 1 ELSE 0 END) AS RiesgoFraude,
            SUM(ISNULL(Total, 0)) AS MontoAuditado
        FROM {db.VIEW_AUDITORIA_CAMBIO_VENDEDOR}
        WHERE {where_sql}
        GROUP BY NivelRiesgo
        ORDER BY
            CASE NivelRiesgo
                WHEN 'Alto' THEN 1
                WHEN 'Medio' THEN 2
                WHEN 'Bajo' THEN 3
                ELSE 4
            END
        """,
        params,
    )


def render() -> None:
    page_title("Auditoria", "Cambio de vendedor, modificaciones posteriores y notas credito")

    min_date, max_date = db.min_max_date()
    default_start = max(min_date, max_date - timedelta(days=31))
    st.sidebar.markdown("### Filtros auditoria")
    start_date = st.sidebar.date_input("Desde", value=default_start, min_value=min_date, max_value=max_date, key="auditoria_desde_v2")
    end_date = st.sidebar.date_input("Hasta", value=max_date, min_value=min_date, max_value=max_date, key="auditoria_hasta_v2")
    only_alerts = st.sidebar.checkbox("Solo alertas", value=True, key="auditoria_solo_alertas_v2")
    risk_levels = st.sidebar.multiselect(
        "Nivel de riesgo",
        ["Alto", "Medio", "Bajo", "Operativo"],
        default=["Alto", "Medio", "Bajo", "Operativo"],
        key="auditoria_riesgo_v2",
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
        key="auditoria_tipo_alerta_v2",
    )
    fraud_only = st.sidebar.checkbox("Solo riesgo fraude", value=False, key="auditoria_solo_fraude_v2")
    branch = st.sidebar.text_input("idSucursal", key="auditoria_sucursal_v2")
    invoice = st.sidebar.text_input("Numero factura", key="auditoria_factura_v2")
    limit = st.sidebar.slider("Registros detalle", min_value=50, max_value=1000, value=250, step=50, key="auditoria_limite_v2")

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
        by_branch = _load_by_branch(where_sql, params)
        change_vendor_users = _load_change_vendor_users(where_sql, params)
        change_vendor_documents = _load_change_vendor_documents(where_sql, params)
        change_vendor_diagnostics = _load_change_vendor_diagnostics(start_date, end_date)
        risk_mix = _load_risk_mix(where_sql, params)
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

    tab_summary, tab_users, tab_branches, tab_detail = st.tabs(
        ["Resumen ejecutivo", "Usuarios", "Sucursales", "Detalle"]
    )

    with tab_summary:
        section_title("Composicion por riesgo")
        display_table(risk_mix, height=220, show_total=True)
        code_footer(*get_code("auditoria", "report"))

    with tab_users:
        section_title("Ranking por usuario modificador")
        display_table(by_user, height=360, show_total=True)
        code_footer(*get_code("auditoria", "users_table"))

        section_title("Ranking de cambios de vendedor")
        if change_vendor_users.empty:
            diagnostic = change_vendor_diagnostics.iloc[0].fillna(0) if not change_vendor_diagnostics.empty else {}
            raw_changes = int(diagnostic.get("DiferenciasVendedor", 0) or 0)
            order_changes = int(diagnostic.get("DiferenciasEnPedidos", 0) or 0)
            auditable_changes = int(diagnostic.get("DiferenciasAuditables", 0) or 0)
            if raw_changes:
                warning_box(
                    "No hay cambios de vendedor auditables con los filtros actuales. "
                    f"WallyBD detecta {number(raw_changes)} diferencia(s) vendedor inicial/final BIT en el rango; "
                    f"{number(order_changes)} son pedidos excluidos por la regla vigente y "
                    f"{number(auditable_changes)} quedan como documentos auditables."
                )
            else:
                warning_box(
                    "No hay cambios de vendedor detectados en WallyBD Mirror para el rango seleccionado. "
                    "La regla compara vendedor inicial contra vendedor final en BITMovimientoInv; las modificaciones posteriores "
                    "del documento aparecen en las alertas de pago, cierre o cambio tardio."
                )
        else:
            display_table(change_vendor_users, height=320, show_total=True)
        code_footer(*get_code("auditoria", "users_table"))

        section_title("Facturas con cambio de vendedor")
        if change_vendor_documents.empty:
            warning_box("No hay facturas con cambio de vendedor para el rango y filtros actuales.")
        else:
            display_table(change_vendor_documents, height=420, show_total=True)
        code_footer(*get_code("auditoria", "detail_table"))

    with tab_branches:
        section_title("Ranking por sucursal")
        display_table(by_branch, height=390, show_total=False)
        code_footer(*get_code("auditoria", "detail_table"))

    with tab_detail:
        section_title("Detalle de alertas")
        if detail.empty:
            warning_box("No hay alertas con los filtros actuales.")
        else:
            _display_audit_detail_table(detail)
            code_footer(*get_code("auditoria", "detail_table"))

    st.download_button(
        "Exportar auditoria a Excel",
        dataframe_to_excel_bytes(
            {
                "Explicacion alertas": _build_plain_language_export(detail),
                "Resumen": summary,
                "Riesgo": risk_mix,
                "Usuarios": by_user,
                "Cambios vendedor": change_vendor_users,
                "Facturas cambio vendedor": change_vendor_documents,
                "Sucursales": by_branch,
                "Detalle": _build_detail_export(detail),
            }
        ),
        file_name=export_filename("wally_auditoria_cambio_vendedor"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
