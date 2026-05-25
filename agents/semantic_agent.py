from __future__ import annotations

from agents.intent_router import normalize_text
from services.local_store import approved_semantic_dictionary, approved_training_entries


INTENT_KEYWORDS = {
    "inventory_by_branch": ["inventario", "existencia", "stock"],
    "inventory_by_shipment": ["inventario", "existencia", "embarque"],
    "inventory_reference": ["inventario", "existencia", "referencia", "codigo"],
    "sales_summary": ["venta", "ventas", "facturacion", "venta neta"],
    "sales_by_branch": ["venta", "ventas", "sucursal", "tienda"],
    "sales_by_seller": ["venta", "ventas", "vendedor", "asesor", "asesora"],
    "sales_by_shipment": ["venta", "ventas", "embarque"],
    "sales_by_line": ["venta", "ventas", "linea", "producto", "tipo prenda"],
    "sales_year_comparison": ["venta", "comparativo", "historico", "anual"],
}


def enrich_question(text: str) -> str:
    normalized = normalize_text(text)
    additions: list[str] = []
    dictionary = approved_semantic_dictionary()
    for _, row in dictionary.iterrows():
        tokens = [row["term"], row.get("definition", ""), row.get("aliases", "")]
        raw_aliases = str(row.get("aliases", "") or "").split(",")
        candidates = [row["term"], *raw_aliases]
        if any(normalize_text(str(candidate)) in normalized for candidate in candidates if str(candidate).strip()):
            additions.extend(str(token) for token in tokens if str(token).strip())
    if not additions:
        return text
    return f"{text} {' '.join(additions)}"


def training_intent_override(text: str) -> str | None:
    normalized = normalize_text(text)
    entries = approved_training_entries()
    for _, row in entries.iterrows():
        question = normalize_text(str(row["question"]))
        if question and (question == normalized or question in normalized or normalized in question):
            return str(row["expected_intent"])
    return None


def infer_intent_from_semantics(text: str) -> str | None:
    normalized = normalize_text(enrich_question(text))
    scores: dict[str, int] = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for keyword in keywords if normalize_text(keyword) in normalized)
        if score:
            scores[intent] = score
    if not scores:
        return None
    return max(scores, key=scores.get)
