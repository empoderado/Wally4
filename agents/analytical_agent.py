from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from agents.intent_router import has_any, normalize_text
from agents.sql_agent import QueryContext, parse_query_context
from agents.temporal_agent import resolve_date_range
from services import db
from services.formatting import money, number, percent


@dataclass(frozen=True)
class AnalyticalPlan:
    title: str
    view: str
    date_column: str | None
    dimensions: list[str]
    measures: dict[str, str]
    display_labels: dict[str, str]
    order_by: str
    params: list
    where_sql: list[str]
    limit: int


SALES_DIMENSIONS = {
    "sucursal": ("Sucursal", ["sucursal", "sucursales", "tienda", "tiendas"]),
    "vendedor": ("Vendedor", ["vendedor", "vendedores", "asesor", "asesora", "asesores", "asesoras"]),
    "cliente": ("Cliente", ["cliente", "clientes"]),
    "referencia": ("Referencia", ["referencia", "referencias", "articulo", "articulos"]),
    "linea": ("Linea", ["linea", "lineas", "producto", "productos"]),
    "tipo_prenda": ("DescripTipoPrenda", ["tipo prenda", "prenda", "prendas"]),
    "embarque": ("CodEmbarqueAbreviado", ["embarque", "embarques"]),
    "coleccion": ("Coleccion_EN", ["coleccion", "colecciones"]),
    "talla": ("Talla", ["talla", "tallas"]),
    "color": ("Color", ["color", "colores"]),
}

INVENTORY_DIMENSIONS = {
    "sucursal": ("Sucursal", ["sucursal", "sucursales", "tienda", "tiendas"]),
    "referencia": ("Referencia", ["referencia", "referencias", "articulo", "articulos"]),
    "linea": ("Linea", ["linea", "lineas", "producto", "productos"]),
    "tipo_prenda": ("DescripTipoPrenda", ["tipo prenda", "prenda", "prendas"]),
    "embarque": ("CodEmbarqueAbreviado", ["embarque", "embarques"]),
    "coleccion": ("Coleccion_EN", ["coleccion", "colecciones"]),
    "talla": ("Talla", ["talla", "tallas"]),
    "color": ("Color", ["color", "colores"]),
}

SALES_MEASURES = {
    "Venta": "SUM(ISNULL(VentaNetaQ, 0))",
    "Unidades": "SUM(ISNULL(Unidades, 0))",
    "Facturas": "COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END)",
    "Margen": "SUM(ISNULL(VentaNetaQ, 0)) - SUM(ISNULL(CostoTotal, 0))",
    "TicketPromedio": "SUM(ISNULL(VentaNetaQ, 0)) / NULLIF(COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END), 0)",
    "UPT": "CAST(SUM(ISNULL(Unidades, 0)) AS decimal(18, 4)) / NULLIF(COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END), 0)",
    "VrUnidadPromedio": "SUM(ISNULL(VentaNetaQ, 0)) / NULLIF(CAST(SUM(ISNULL(Unidades, 0)) AS decimal(18, 4)), 0)",
    "PorcMargen": "(SUM(ISNULL(VentaNetaQ, 0)) - SUM(ISNULL(CostoTotal, 0))) / NULLIF(CAST(SUM(ISNULL(VentaNetaQ, 0)) AS decimal(18, 4)), 0)",
}

INVENTORY_MEASURES = {
    "ExistenciaFisica": "SUM(ISNULL(ExistenciaFisica, 0))",
    "ExistenciaDisponible": "SUM(ISNULL(ExistenciaDisponible, 0))",
    "TVida": "MIN(ISNULL(TVida, 0))",
}

SALES_LABELS = {
    "Venta": "Venta",
    "Unidades": "Unid",
    "Facturas": "Fact",
    "Margen": "Margen",
    "TicketPromedio": "Ticket",
    "UPT": "UPT",
    "VrUnidadPromedio": "Vr Unid",
    "PorcMargen": "% Margen",
}

INVENTORY_LABELS = {
    "ExistenciaFisica": "Fisica",
    "ExistenciaDisponible": "Disponible",
    "TVida": "TVida",
}


def try_answer(question: str) -> str | None:
    result = try_result(question)
    return result.answer if result else None


@dataclass(frozen=True)
class AnalyticalResult:
    plan: AnalyticalPlan
    dataframe: pd.DataFrame
    answer: str


def try_result(question: str) -> AnalyticalResult | None:
    plan = build_plan(question)
    if not plan:
        return None
    df = execute_plan(plan)
    return AnalyticalResult(plan, df, render_plan_answer(plan, df))


def should_prefer_analytical(question: str, intent: str) -> bool:
    normalized = normalize_text(question)
    if intent == "unknown":
        return True
    if has_any(normalized, ["tipo prenda", "referencia", "referencias", "coleccion", "color", "talla"]):
        return True
    if has_any(normalized, ["ticket", "upt", "unidad promedio", "vr unidad", "rentabilidad", "margen"]):
        return True
    if intent == "inventory_by_branch" and has_any(normalized, ["por linea", "por color", "por talla", "por coleccion", "por tipo prenda"]):
        return True
    return False


def build_plan(question: str) -> AnalyticalPlan | None:
    normalized = normalize_text(question)
    context = parse_query_context(question)
    if _is_inventory_question(normalized):
        return _build_inventory_plan(question, normalized, context)
    if _is_sales_question(normalized):
        return _build_sales_plan(question, normalized, context)
    return None


def execute_plan(plan: AnalyticalPlan) -> pd.DataFrame:
    select_parts = [*plan.dimensions]
    for alias, expression in plan.measures.items():
        select_parts.append(f"{expression} AS {alias}")

    query = f"""
        SELECT
            {", ".join(select_parts)}
        FROM {plan.view}
    """
    if plan.where_sql:
        query += "\n        WHERE " + "\n          AND ".join(plan.where_sql)
    if plan.dimensions:
        query += "\n        GROUP BY " + ", ".join(plan.dimensions)
    query += f"\n        ORDER BY {plan.order_by} DESC"

    return db.read_sql(query, plan.params)


def render_plan_answer(plan: AnalyticalPlan, df: pd.DataFrame) -> str:
    if df.empty:
        return f"No encontre datos para **{plan.title}**."

    visible = df.head(plan.limit)
    lines = [f"**{plan.title}**"]
    dimension = plan.dimensions[0] if plan.dimensions else None
    measure_names = list(plan.measures.keys())

    for position, (_, row) in enumerate(visible.iterrows(), start=1):
        label = _row_label(row, plan.dimensions) if dimension else "Total"
        values = [_format_measure(name, row[name]) for name in measure_names]
        lines.append(f"\n{position}. **{label}**: " + " | ".join(values))

    total_values = []
    for name in measure_names:
        total_values.append(_format_total_measure(name, df, plan.measures))
    lines.append("\n**Total:** " + " | ".join(total_values))
    return "\n".join(lines)


def _build_sales_plan(question: str, normalized: str, context: QueryContext) -> AnalyticalPlan:
    dates = resolve_date_range(question)
    dimensions = _detect_dimensions(normalized, SALES_DIMENSIONS) or ["Sucursal"]
    measures = _detect_sales_measures(normalized)
    order_by = _detect_order_by(normalized, measures)
    where_sql = ["Fecha >= ? AND Fecha < DATEADD(day, 1, ?)", "Trn = 'FV'"]
    params: list = [dates.start, dates.end]
    if context.branch:
        where_sql.append("Sucursal = ?")
        params.append(context.branch)
    if context.reference:
        where_sql.append("Referencia = ?")
        params.append(context.reference)

    return AnalyticalPlan(
        title=f"Consulta analitica de ventas {dates.label} [{dates.start}; {dates.end}]",
        view=db.VIEW_VENTAS,
        date_column="Fecha",
        dimensions=dimensions,
        measures=measures,
        display_labels=SALES_LABELS,
        order_by=order_by,
        params=params,
        where_sql=where_sql,
        limit=context.limit,
    )


def _build_inventory_plan(question: str, normalized: str, context: QueryContext) -> AnalyticalPlan:
    dimensions = _detect_dimensions(normalized, INVENTORY_DIMENSIONS) or ["Sucursal"]
    where_sql: list[str] = []
    params: list = []
    if context.branch:
        where_sql.append("Sucursal = ?")
        params.append(context.branch)
    if context.reference:
        where_sql.append("Referencia = ?")
        params.append(context.reference)

    return AnalyticalPlan(
        title="Consulta analitica de inventario",
        view=db.VIEW_EXISTENCIA,
        date_column=None,
        dimensions=dimensions,
        measures=INVENTORY_MEASURES,
        display_labels=INVENTORY_LABELS,
        order_by="ExistenciaFisica",
        params=params,
        where_sql=where_sql,
        limit=context.limit,
    )


def _detect_dimensions(normalized: str, catalog: dict[str, tuple[str, list[str]]]) -> list[str]:
    dimensions: list[str] = []
    for _, (column, aliases) in catalog.items():
        if any(alias in normalized for alias in aliases):
            dimensions.append(column)
    return dimensions[:2]


def _detect_sales_measures(normalized: str) -> dict[str, str]:
    measures: dict[str, str] = {}
    if has_any(normalized, ["venta", "ventas", "vendido", "vendida", "vendidos", "vendidas", "facturacion", "quetzales", "q "]):
        measures["Venta"] = SALES_MEASURES["Venta"]
    if has_any(normalized, ["unidad", "unidades", "piezas"]):
        measures["Unidades"] = SALES_MEASURES["Unidades"]
    if has_any(normalized, ["factura", "facturas", "veces", "compras", "comprado", "compraron"]):
        measures["Facturas"] = SALES_MEASURES["Facturas"]
    if has_any(normalized, ["margen", "rentabilidad"]):
        measures["Margen"] = SALES_MEASURES["Margen"]
        measures["PorcMargen"] = SALES_MEASURES["PorcMargen"]
    if has_any(normalized, ["ticket", "factura promedio"]):
        measures["TicketPromedio"] = SALES_MEASURES["TicketPromedio"]
    if "upt" in normalized:
        measures["UPT"] = SALES_MEASURES["UPT"]
    if has_any(normalized, ["unidad promedio", "vr unidad", "valor promedio unidad"]):
        measures["VrUnidadPromedio"] = SALES_MEASURES["VrUnidadPromedio"]
    return measures or {"Venta": SALES_MEASURES["Venta"], "Unidades": SALES_MEASURES["Unidades"], "Facturas": SALES_MEASURES["Facturas"]}


def _detect_order_by(normalized: str, measures: dict[str, str]) -> str:
    if has_any(normalized, ["veces", "factura", "facturas", "frecuencia", "compras", "comprado", "compraron"]) and "Facturas" in measures:
        return "Facturas"
    if has_any(normalized, ["unidad", "unidades"]) and "Unidades" in measures:
        return "Unidades"
    if has_any(normalized, ["margen", "rentabilidad"]) and "Margen" in measures:
        return "Margen"
    return next(iter(measures.keys()))


def _is_inventory_question(normalized: str) -> bool:
    return has_any(normalized, ["inventario", "existencia", "existencias", "stock"])


def _is_sales_question(normalized: str) -> bool:
    return has_any(
        normalized,
        [
            "venta",
            "ventas",
            "vendido",
            "vendida",
            "vendidos",
            "vendidas",
            "facturacion",
            "cliente",
            "clientes",
            "compras",
            "comprado",
            "compraron",
            "ticket",
            "upt",
            "margen",
            "rentabilidad",
            "unidad promedio",
            "vr unidad",
        ],
    )


def _format_measure(name: str, value) -> str:
    label = SALES_LABELS.get(name) or INVENTORY_LABELS.get(name) or name
    if name in {"Venta", "Margen", "TicketPromedio", "VrUnidadPromedio"}:
        return f"{label} {money(value)}"
    if name in {"ExistenciaFisica", "ExistenciaDisponible"}:
        return f"{label} {number(value)}"
    if name == "TVida":
        return f"{label} {number(value)} dias"
    if name.lower().startswith("porc"):
        return f"{label} {percent(value)}"
    return f"{label} {number(value, 2) if name == 'UPT' else number(value)}"


def _format_total_measure(name: str, df: pd.DataFrame, measures: dict[str, str]) -> str:
    if name == "TicketPromedio":
        facturas = df["Facturas"].sum() if "Facturas" in df.columns else 0
        venta = df["Venta"].sum() if "Venta" in df.columns else 0
        return _format_measure(name, venta / facturas if facturas else 0)
    if name == "UPT":
        facturas = df["Facturas"].sum() if "Facturas" in df.columns else 0
        unidades = df["Unidades"].sum() if "Unidades" in df.columns else 0
        return _format_measure(name, unidades / facturas if facturas else 0)
    if name == "VrUnidadPromedio":
        unidades = df["Unidades"].sum() if "Unidades" in df.columns else 0
        venta = df["Venta"].sum() if "Venta" in df.columns else 0
        return _format_measure(name, venta / unidades if unidades else 0)
    if name == "PorcMargen":
        margen = df["Margen"].sum() if "Margen" in df.columns else 0
        venta = df["Venta"].sum() if "Venta" in df.columns else 0
        return _format_measure(name, margen / venta if venta else 0)
    if name == "TVida":
        return _format_measure(name, df[name].min())
    return _format_measure(name, df[name].sum())


def _row_label(row: pd.Series, dimensions: list[str]) -> str:
    values = [str(row[dimension]) for dimension in dimensions if dimension in row and pd.notna(row[dimension])]
    return " | ".join(values) if values else "Sin dato"
