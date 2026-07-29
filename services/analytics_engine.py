from __future__ import annotations

import json
import re
import unicodedata
from calendar import monthrange
from datetime import date

import pandas as pd

from services import db


VENTAS_DIMENSIONS = {
    "anio": "YEAR(CAST(Fecha AS date))",
    "mes": "MONTH(CAST(Fecha AS date))",
    "fecha": "CAST(Fecha AS date)",
    "sucursal": "Sucursal",
    "vendedor": "Vendedor",
    "linea": "Linea",
    "tipo_prenda": "DescripTipoPrenda",
    "embarque": "CodEmbarqueAbreviado",
    "coleccion": "Coleccion_EN",
    "referencia": "Referencia",
}

VENTAS_METRICS = {
    "venta_neta": "SUM(ISNULL(VentaNetaQ, 0))",
    "unidades": "SUM(ISNULL(Unidades, 0))",
    "facturas": "COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END)",
    "venta_bruta": "SUM(ISNULL(VentaBruta, 0))",
    "descuento": "SUM(ISNULL(DescuentoValor, 0))",
    "costo": "SUM(ISNULL(CostoTotal, 0))",
    "margen": "SUM(ISNULL(VentaNetaQ, 0)) / 1.12 - SUM(ISNULL(CostoTotal, 0))",
    "ticket_promedio": "SUM(ISNULL(VentaNetaQ, 0)) / NULLIF(COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END), 0)",
    "upt": "CAST(SUM(ISNULL(Unidades, 0)) AS decimal(18, 4)) / NULLIF(COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END), 0)",
    "vr_unidad_promedio": "SUM(ISNULL(VentaNetaQ, 0)) / NULLIF(SUM(ISNULL(Unidades, 0)), 0)",
    "porc_margen": "(SUM(ISNULL(VentaNetaQ, 0)) / 1.12 - SUM(ISNULL(CostoTotal, 0))) / NULLIF(SUM(ISNULL(VentaNetaQ, 0)) / 1.12, 0)",
}

EXISTENCIA_DIMENSIONS = {
    "sucursal": "Sucursal",
    "referencia": "Referencia",
    "linea": "Linea",
    "tipo_prenda": "DescripTipoPrenda",
    "embarque": "CodEmbarqueAbreviado",
    "coleccion": "Coleccion_EN",
    "talla": "Talla",
    "color": "Color",
}

EXISTENCIA_METRICS = {
    "existencia_fisica": "SUM(ExistenciaFisica)",
    "existencia_disponible": "SUM(ExistenciaDisponible)",
    "referencias": "COUNT(DISTINCT Referencia)",
    "embarques": "COUNT(DISTINCT CodEmbarqueAbreviado)",
    "tvida": "MIN(TVida)",
}

SALES_SYNONYMS = {
    "venta": "venta_neta",
    "ventas": "venta_neta",
    "facturacion": "venta_neta",
    "facturaciÃ³n": "venta_neta",
    "unid": "unidades",
    "unidad": "unidades",
    "unidades": "unidades",
    "factura": "facturas",
    "facturas": "facturas",
    "margen": "margen",
    "ticket": "ticket_promedio",
    "upt": "upt",
    "precio promedio": "vr_unidad_promedio",
}

DIMENSION_SYNONYMS = {
    "aÃ±o": "anio",
    "anio": "anio",
    "mes": "mes",
    "fecha": "fecha",
    "dia": "fecha",
    "dÃ­a": "fecha",
    "sucursal": "sucursal",
    "tienda": "sucursal",
    "vendedor": "vendedor",
    "asesor": "vendedor",
    "asesora": "vendedor",
    "linea": "linea",
    "lÃ­nea": "linea",
    "tipo": "tipo_prenda",
    "tipo prenda": "tipo_prenda",
    "embarque": "embarque",
    "coleccion": "coleccion",
    "colecciÃ³n": "coleccion",
    "referencia": "referencia",
}


def _records(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    return json.loads(df.where(pd.notna(df), None).to_json(orient="records", date_format="iso"))


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return value.lower()


def _safe_items(values: list[str], allowed: dict[str, str], fallback: list[str]) -> list[str]:
    selected = []
    for value in values or []:
        value = str(value).strip().lower()
        if value in allowed and value not in selected:
            selected.append(value)
    return selected or fallback


def consulta_ventas(
    dimensiones: list[str] | None = None,
    metricas: list[str] | None = None,
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    top: int = 50,
    ordenar_por: str = "venta_neta",
    descendente: bool = True,
) -> dict:
    dims = _safe_items(dimensiones or [], VENTAS_DIMENSIONS, [])
    mets = _safe_items(metricas or [], VENTAS_METRICS, ["venta_neta", "unidades", "facturas"])
    top = max(1, min(int(top or 50), 100))
    today = date.today()
    start = fecha_inicio or date(today.year, 1, 1).isoformat()
    end = fecha_fin or today.isoformat()

    select_dims = [f"{VENTAS_DIMENSIONS[dim]} AS {dim}" for dim in dims]
    select_mets = [f"{VENTAS_METRICS[met]} AS {met}" for met in mets]
    group_by = ", ".join(VENTAS_DIMENSIONS[dim] for dim in dims)
    order_metric = ordenar_por if ordenar_por in mets else mets[0]
    order_dir = "DESC" if descendente else "ASC"
    top_clause = f"TOP ({top})" if dims else ""
    query = f"""
        SELECT {top_clause}
            {", ".join(select_dims + select_mets)}
        FROM {db.VIEW_VENTAS}
        WHERE Fecha >= ? AND Fecha < DATEADD(day, 1, ?)
        {"GROUP BY " + group_by if group_by else ""}
        ORDER BY {order_metric} {order_dir}
    """
    df = db.read_sql(query, (start, end))
    return {
        "tipo": "consulta_ventas",
        "fuente": db.VIEW_VENTAS,
        "rango": [start, end],
        "dimensiones": dims,
        "metricas": mets,
        "datos": _records(df),
    }


def consulta_existencias(
    dimensiones: list[str] | None = None,
    metricas: list[str] | None = None,
    top: int = 50,
    ordenar_por: str = "existencia_fisica",
    descendente: bool = True,
) -> dict:
    dims = _safe_items(dimensiones or [], EXISTENCIA_DIMENSIONS, ["sucursal"])
    mets = _safe_items(metricas or [], EXISTENCIA_METRICS, ["existencia_fisica", "existencia_disponible"])
    top = max(1, min(int(top or 50), 100))
    select_dims = [f"{EXISTENCIA_DIMENSIONS[dim]} AS {dim}" for dim in dims]
    select_mets = [f"{EXISTENCIA_METRICS[met]} AS {met}" for met in mets]
    group_by = ", ".join(EXISTENCIA_DIMENSIONS[dim] for dim in dims)
    order_metric = ordenar_por if ordenar_por in mets else mets[0]
    order_dir = "DESC" if descendente else "ASC"
    query = f"""
        SELECT TOP ({top})
            {", ".join(select_dims + select_mets)}
        FROM {db.VIEW_EXISTENCIA}
        GROUP BY {group_by}
        ORDER BY {order_metric} {order_dir}
    """
    df = db.read_sql(query)
    return {
        "tipo": "consulta_existencias",
        "fuente": db.VIEW_EXISTENCIA,
        "dimensiones": dims,
        "metricas": mets,
        "datos": _records(df),
    }


def comparativo_ventas_anual(ultimos_anios: int = 4) -> dict:
    today = date.today()
    years = max(1, min(int(ultimos_anios or 4), 10))
    start_year = today.year - years + 1
    df = db.read_sql(
        f"""
        SELECT
            YEAR(CAST(Fecha AS date)) AS Anio,
            SUM(ISNULL(VentaNetaQ, 0)) AS VentaNetaQ,
            SUM(ISNULL(Unidades, 0)) AS Unidades,
            COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END) AS Facturas,
            SUM(ISNULL(VentaNetaQ, 0)) / 1.12 - SUM(ISNULL(CostoTotal, 0)) AS MargenQ,
            (SUM(ISNULL(VentaNetaQ, 0)) / 1.12 - SUM(ISNULL(CostoTotal, 0))) / NULLIF(SUM(ISNULL(VentaNetaQ, 0)) / 1.12, 0) AS PorcMargen
        FROM {db.VIEW_VENTAS}
        WHERE YEAR(CAST(Fecha AS date)) BETWEEN ? AND ?
        GROUP BY YEAR(CAST(Fecha AS date))
        ORDER BY Anio
        """,
        (start_year, today.year),
    )
    if not df.empty:
        df["VariacionVentaPct"] = df["VentaNetaQ"].pct_change()
    return {
        "tipo": "comparativo_ventas_anual",
        "fuente": db.VIEW_VENTAS,
        "periodo": [start_year, today.year],
        "datos": _records(df),
    }


def proyeccion_mes_por_sucursal(anio: int | None = None, mes: int | None = None) -> dict:
    today = date.today()
    anio = int(anio or today.year)
    mes = int(mes or today.month)
    first_day = date(anio, mes, 1)
    last_day = date(anio, mes, monthrange(anio, mes)[1])
    end_day = min(today, last_day) if anio == today.year and mes == today.month else last_day
    elapsed_days = max(1, (end_day - first_day).days + 1)
    total_days = monthrange(anio, mes)[1]
    df = db.read_sql(
        f"""
        SELECT
            Sucursal,
            SUM(ISNULL(VentaNetaQ, 0)) AS VentaAcumuladaQ,
            SUM(ISNULL(Unidades, 0)) AS Unidades,
            COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END) AS Facturas,
            SUM(ISNULL(VentaNetaQ, 0)) / NULLIF(COUNT(DISTINCT CAST(Fecha AS date)), 0) AS PromedioDiaConVentaQ,
            COUNT(DISTINCT CAST(Fecha AS date)) AS DiasConVenta
        FROM {db.VIEW_VENTAS}
        WHERE Fecha >= ? AND Fecha < DATEADD(day, 1, ?)
        GROUP BY Sucursal
        ORDER BY VentaAcumuladaQ DESC
        """,
        (first_day.isoformat(), end_day.isoformat()),
    )
    if not df.empty:
        df["PromedioCalendarioQ"] = df["VentaAcumuladaQ"] / elapsed_days
        df["ProyeccionCierreQ"] = df["PromedioCalendarioQ"] * total_days
        total_projection = float(df["ProyeccionCierreQ"].sum() or 0)
        df["ParticipacionProyectadaPct"] = df["ProyeccionCierreQ"] / total_projection if total_projection else 0
    return {
        "tipo": "proyeccion_mes_por_sucursal",
        "fuente": db.VIEW_VENTAS,
        "periodo": [first_day.isoformat(), end_day.isoformat()],
        "dias_transcurridos": elapsed_days,
        "dias_mes": total_days,
        "datos": _records(df),
    }




def inferir_consulta(question: str) -> dict | None:
    text = _norm(question)
    if any(word in text for word in ("comparativo", "compara", "comparar")) and any(word in text for word in ("ano", "anios", "anual")) and "venta" in text:
        match = next((int(value) for value in re.findall(r"\b(\d{1,2})\b", text) if int(value) <= 10), 4)
        return comparativo_ventas_anual(match)
    if "venta" in text and any(word in text for word in ("ano", "anios", "anual")) and any(word in text for word in ("ultimos", "ultimas")):
        match = next((int(value) for value in re.findall(r"\b(\d{1,2})\b", text) if int(value) <= 10), 4)
        return comparativo_ventas_anual(match)
    if any(word in text for word in ("proyecta", "proyeccion", "cierre")) and "venta" in text and "sucursal" in text:
        return proyeccion_mes_por_sucursal()
    return None
