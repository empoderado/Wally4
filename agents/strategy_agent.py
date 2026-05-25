from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from agents.intent_router import has_any, normalize_text
from memory.store import recent_conversations
from services.formatting import money, number, percent


STRATEGY_TERMS = [
    "analiza",
    "analisis",
    "estrategia",
    "estrategias",
    "plan de accion",
    "plan accion",
    "recomendacion",
    "recomendaciones",
    "mejorar",
    "mejora",
    "que hacemos",
    "que debo hacer",
    "acciones",
]

PREVIOUS_TERMS = [
    "lo anterior",
    "la respuesta anterior",
    "estos resultados",
    "ese resultado",
    "esa respuesta",
]


@dataclass(frozen=True)
class StrategyContext:
    title: str
    dataframe: pd.DataFrame | None = None
    answer_text: str = ""


def wants_strategy(question: str) -> bool:
    return has_any(normalize_text(question), STRATEGY_TERMS)


def wants_previous_context(question: str) -> bool:
    return has_any(normalize_text(question), PREVIOUS_TERMS)


def strategy_from_result(question: str, context: StrategyContext) -> str:
    if context.dataframe is not None and not context.dataframe.empty:
        return _strategy_from_dataframe(question, context)
    if context.answer_text.strip():
        return _strategy_from_text(context.answer_text)
    return _default_strategy()


def strategy_from_previous(user_id: str | None = None) -> str | None:
    history = recent_conversations(limit=3, user_id=user_id or None)
    if history.empty:
        return None
    for _, row in history.iterrows():
        answer = str(row.get("answer", "") or "").strip()
        if answer and "Todavia no tengo" not in answer:
            return _strategy_from_text(answer)
    return None


def _strategy_from_dataframe(question: str, context: StrategyContext) -> str:
    df = context.dataframe.copy()
    normalized = normalize_text(question)
    lines = [f"**Analisis estrategico de {context.title}**"]

    if _has_sales_columns(df):
        lines.extend(_sales_insights(df))
    elif _has_inventory_columns(df):
        lines.extend(_inventory_insights(df))
    else:
        lines.extend(_generic_insights(df))

    if has_any(normalized, ["plan", "accion", "acciones", "estrategia", "mejorar", "recomendacion"]):
        lines.extend(_action_plan(df, normalized))

    return "\n\n".join(lines)


def _sales_insights(df: pd.DataFrame) -> list[str]:
    venta_col = _first_existing(df, ["VentaNetaQ", "Venta"])
    unidades_col = _first_existing(df, ["Unidades"])
    facturas_col = _first_existing(df, ["Facturas"])
    margen_col = _first_existing(df, ["MargenQ", "Margen"])
    label_col = _best_label_column(df)

    total_venta = df[venta_col].sum() if venta_col else 0
    total_unidades = df[unidades_col].sum() if unidades_col else 0
    total_facturas = df[facturas_col].sum() if facturas_col else 0
    total_margen = df[margen_col].sum() if margen_col else 0

    summary_parts = []
    if venta_col:
        summary_parts.append(f"venta total {money(total_venta)}")
    if unidades_col:
        summary_parts.append(f"unidades {number(total_unidades)}")
    if facturas_col:
        summary_parts.append(f"facturas {number(total_facturas)}")
    if margen_col:
        summary_parts.append(f"margen {money(total_margen)}")
    lines = [f"**Resumen:** {', '.join(summary_parts)}."]

    if venta_col and label_col:
        ranked = df.sort_values(venta_col, ascending=False)
        top = ranked.iloc[0]
        low = ranked.iloc[-1]
        top_share = top[venta_col] / total_venta if total_venta else 0
        lines.append(
            f"**Lectura clave:** {top[label_col]} lidera con {money(top[venta_col])}, equivalente al {percent(top_share)} de la venta analizada."
        )
        if len(ranked) > 1:
            lines.append(f"**Alerta:** {low[label_col]} queda al final con {money(low[venta_col])}; conviene revisar trafico, conversion, inventario y ejecucion comercial.")
    elif margen_col and label_col:
        ranked = df.sort_values(margen_col, ascending=False)
        top = ranked.iloc[0]
        low = ranked.iloc[-1]
        lines.append(f"**Lectura clave:** {top[label_col]} lidera en margen con {money(top[margen_col])}.")
        if len(ranked) > 1:
            lines.append(f"**Alerta:** {low[label_col]} queda al final en margen con {money(low[margen_col])}; revisar descuentos, costo y mezcla de producto.")

    if margen_col and venta_col and total_venta:
        margen_pct = total_margen / total_venta
        lines.append(f"**Rentabilidad:** el margen consolidado es {percent(margen_pct)}.")

    return lines


def _inventory_insights(df: pd.DataFrame) -> list[str]:
    fisica_col = _first_existing(df, ["ExistenciaFisica", "Existencia"])
    disponible_col = _first_existing(df, ["ExistenciaDisponible"])
    label_col = _best_label_column(df)
    total_fisica = df[fisica_col].sum() if fisica_col else 0
    total_disponible = df[disponible_col].sum() if disponible_col else 0
    if disponible_col:
        lines = [f"**Resumen:** existencia fisica total {number(total_fisica)} y disponible {number(total_disponible)}."]
    else:
        lines = [f"**Resumen:** existencia fisica total {number(total_fisica)}."]
    if fisica_col and label_col:
        ranked = df.sort_values(fisica_col, ascending=False)
        top = ranked.iloc[0]
        low = ranked.iloc[-1]
        lines.append(f"**Lectura clave:** {top[label_col]} concentra la mayor existencia con {number(top[fisica_col])} unidades.")
        if len(ranked) > 1:
            lines.append(f"**Alerta:** {low[label_col]} tiene baja existencia ({number(low[fisica_col])}); validar si requiere reposicion o traslado.")
    return lines


def _generic_insights(df: pd.DataFrame) -> list[str]:
    return [
        f"**Resumen:** se analizaron {number(len(df))} registros.",
        "**Lectura clave:** la informacion esta disponible, pero no identifique columnas comerciales suficientes para calcular venta, margen o inventario.",
    ]


def _action_plan(df: pd.DataFrame, normalized_question: str) -> list[str]:
    if _has_inventory_columns(df) or "inventario" in normalized_question:
        return [
            "**Plan de accion:**",
            "1. Priorizar traslados desde sucursales con mayor existencia hacia puntos con menor disponibilidad.",
            "2. Revisar referencias con alta existencia y baja salida para activar exhibicion, venta asistida o promocion controlada.",
            "3. Separar productos con disponibilidad cero para evitar prometer mercancia que no puede venderse.",
            "4. Validar semanalmente embarques de mayor TVida para acelerar rotacion antes de aplicar descuento amplio.",
        ]
    return [
        "**Plan de accion:**",
        "1. Enfocar seguimiento diario en los grupos con mayor venta para proteger el resultado principal.",
        "2. Revisar los grupos de menor desempeno y confirmar si el problema es trafico, inventario, conversion o disciplina comercial.",
        "3. Replicar practicas del lider en los puntos rezagados: mix de producto, exhibicion, argumentario y cierre.",
        "4. Definir una meta puntual para el siguiente corte y medir avance contra venta, unidades, facturas y margen.",
    ]


def _strategy_from_text(answer_text: str) -> str:
    return (
        "**Analisis estrategico sobre la respuesta anterior**\n\n"
        "1. La respuesta previa ya entrega una base cuantitativa; el primer paso es identificar el lider, el rezagado y el total general.\n\n"
        "2. Si el indicador principal es venta, prioriza acciones sobre conversion, ticket promedio y disponibilidad de producto.\n\n"
        "3. Si el indicador principal es inventario, prioriza rotacion, traslado entre sucursales y control de productos con baja disponibilidad.\n\n"
        "4. Si hay diferencias fuertes entre sucursales, compara mix de producto, vendedor responsable, trafico y horarios de mayor facturacion.\n\n"
        "5. Accion recomendada: pide a Mar-IA el desglose por sucursal, vendedor, linea o referencia para ubicar la causa exacta."
    )


def _default_strategy() -> str:
    return (
        "**Analisis estrategico**\n\n"
        "Necesito primero una consulta de ventas, inventario, clientes o presupuesto para proponer acciones con datos de Wally."
    )


def _has_sales_columns(df: pd.DataFrame) -> bool:
    return bool(_first_existing(df, ["VentaNetaQ", "Venta", "MargenQ", "Margen"]))


def _has_inventory_columns(df: pd.DataFrame) -> bool:
    return bool(_first_existing(df, ["ExistenciaFisica", "Existencia", "ExistenciaDisponible"]))


def _first_existing(df: pd.DataFrame, columns: list[str]) -> str | None:
    return next((column for column in columns if column in df.columns), None)


def _best_label_column(df: pd.DataFrame) -> str | None:
    candidates = [
        "Sucursal",
        "Vendedor",
        "Cliente",
        "Referencia",
        "Linea",
        "DescripTipoPrenda",
        "CodEmbarqueAbreviado",
        "Coleccion_EN",
        "Color",
        "Talla",
    ]
    return _first_existing(df, candidates)
