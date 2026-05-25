from __future__ import annotations

import unicodedata


def detect_intent(text: str) -> str:
    from agents.semantic_agent import enrich_question, infer_intent_from_semantics, training_intent_override

    override = training_intent_override(text)
    if override:
        return override

    text = enrich_question(text)
    normalized = normalize_text(text)

    if has_any(normalized, ["borrar", "eliminar", "actualizar base", "modificar base", "drop", "delete", "update"]):
        return "forbidden"

    if has_any(normalized, ["inventario", "existencia", "stock"]):
        if has_any(normalized, ["embarque", "embarques"]):
            return "inventory_by_shipment"
        if has_any(normalized, ["referencia", "ref ", "codigo"]):
            return "inventory_reference"
        return "inventory_by_branch"

    if has_any(normalized, ["cliente", "clientes"]):
        if has_any(normalized, ["mejor", "top", "ranking", "mayor", "principales"]):
            return "best_customer"
        return "best_customer"

    if has_any(normalized, ["venta", "ventas", "facturacion"]):
        if has_any(normalized, ["comparativo", "comparar", "historico", "ultimos 4", "anos", "anual"]):
            return "sales_year_comparison"
        if has_any(normalized, ["vendedor", "asesor", "asesora"]):
            return "sales_by_seller"
        if has_any(normalized, ["embarque", "embarques"]):
            return "sales_by_shipment"
        if has_any(normalized, ["linea", "tipo prenda", "producto"]):
            return "sales_by_line"
        if has_any(normalized, ["sucursal", "tienda", "por sucursal"]):
            return "sales_by_branch"
        return "sales_summary"

    if has_any(normalized, ["ayuda", "que puedes hacer", "opciones"]):
        return "help"

    return infer_intent_from_semantics(text) or "unknown"


def has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    without_accents = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return without_accents.lower().strip()
