from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
import re

import pandas as pd

from agents.intent_router import has_any, normalize_text
from agents.sql_agent import parse_query_context
from agents.temporal_agent import DateRange
from services.local_store import connect


@dataclass(frozen=True)
class ConversationContext:
    user_id: str
    domain: str
    intent: str
    title: str
    answer_text: str
    dataframe: pd.DataFrame
    date_start: date | None
    date_end: date | None
    date_label: str
    branch: str | None
    reference: str | None
    focus_entity: str | None
    focus_label: str | None


def save_result_context(
    *,
    user_id: str,
    domain: str,
    intent: str,
    title: str,
    answer_text: str,
    dataframe: pd.DataFrame | None,
    dates: DateRange | None = None,
    branch: str | None = None,
    reference: str | None = None,
) -> None:
    _ensure_table()
    frame = dataframe.copy() if dataframe is not None else pd.DataFrame()
    payload = frame.where(pd.notna(frame), None).to_dict(orient="records")
    conn = connect()
    try:
        conn.execute(
            """
            INSERT INTO maria_conversation_context
                (
                    user_id, domain, intent, title, answer_text, result_json,
                    date_start, date_end, date_label, branch, reference,
                    focus_entity, focus_label, updated_at
                )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                domain = excluded.domain,
                intent = excluded.intent,
                title = excluded.title,
                answer_text = excluded.answer_text,
                result_json = excluded.result_json,
                date_start = excluded.date_start,
                date_end = excluded.date_end,
                date_label = excluded.date_label,
                branch = excluded.branch,
                reference = excluded.reference,
                focus_entity = NULL,
                focus_label = NULL,
                updated_at = excluded.updated_at
            """,
            (
                user_id or "anonymous",
                domain,
                intent,
                title,
                answer_text,
                json.dumps(payload, ensure_ascii=True, default=str),
                dates.start.isoformat() if dates else None,
                dates.end.isoformat() if dates else None,
                dates.label if dates else "",
                branch,
                reference,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def load_result_context(user_id: str) -> ConversationContext | None:
    _ensure_table()
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM maria_conversation_context WHERE user_id = ?",
            (user_id or "anonymous",),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    records = json.loads(row["result_json"] or "[]")
    return ConversationContext(
        user_id=row["user_id"],
        domain=row["domain"] or "",
        intent=row["intent"] or "",
        title=row["title"] or "",
        answer_text=row["answer_text"] or "",
        dataframe=pd.DataFrame(records),
        date_start=date.fromisoformat(row["date_start"]) if row["date_start"] else None,
        date_end=date.fromisoformat(row["date_end"]) if row["date_end"] else None,
        date_label=row["date_label"] or "",
        branch=row["branch"],
        reference=row["reference"],
        focus_entity=row["focus_entity"],
        focus_label=row["focus_label"],
    )


def clear_result_context(user_id: str) -> None:
    _ensure_table()
    conn = connect()
    try:
        conn.execute(
            "DELETE FROM maria_conversation_context WHERE user_id = ?",
            (user_id or "anonymous",),
        )
        conn.commit()
    finally:
        conn.close()


def contextualize_question(text: str, user_id: str) -> tuple[str, ConversationContext | None]:
    context = load_result_context(user_id)
    normalized = normalize_text(text)
    query_context = parse_query_context(text)
    additions: list[str] = []
    enriched_text = text

    if not context:
        if query_context.branch and _is_follow_up(normalized) and not _has_domain(normalized):
            return f"{text} ventas", None
        return text, None

    branch = query_context.branch
    if not branch and context.focus_label == "Sucursal" and context.focus_entity and _uses_context_reference(normalized):
        branch = context.focus_entity
    if not branch and context.branch and _uses_context_reference(normalized):
        branch = context.branch
    if branch and _uses_context_reference(normalized):
        enriched_text = re.sub(
            r"(?i)\b(esa sucursal|la sucursal anterior)\b",
            branch,
            enriched_text,
        )
    if branch and normalize_text(branch) not in normalize_text(enriched_text):
        additions.append(branch)

    if not _has_domain(normalized) and _is_follow_up(normalized):
        additions.append("inventario" if context.domain == "inventory" else "ventas")

    if not additions:
        return enriched_text, context
    return f"{enriched_text} {' '.join(additions)}", context


def answer_from_context(text: str, user_id: str) -> str | None:
    context = load_result_context(user_id)
    if not context or context.dataframe.empty:
        return None
    normalized = normalize_text(text)
    wants_low = has_any(normalized, ["cual quedo peor", "cual fue peor", "la peor", "el peor", "menor venta", "mas bajo", "rezagado"])
    wants_high = has_any(normalized, ["cual quedo mejor", "cual fue mejor", "la mejor", "el mejor", "mayor venta", "mas alto", "lider"])
    if not wants_low and not wants_high:
        return None

    metric = _metric_column(context.dataframe)
    label = _label_column(context.dataframe)
    if not metric or not label:
        return None

    values = pd.to_numeric(context.dataframe[metric], errors="coerce")
    if values.dropna().empty:
        return None
    index = values.idxmin() if wants_low else values.idxmax()
    row = context.dataframe.loc[index]
    entity = str(row[label])
    _set_focus(user_id, entity, label)
    position = "menor" if wants_low else "mayor"
    return (
        f"**{entity}** tiene el {position} resultado de la consulta anterior "
        f"en **{metric}**, con **{_format_value(metric, row[metric])}**."
    )


def dates_from_context(text: str, context: ConversationContext | None) -> DateRange | None:
    if not context or not context.date_start or not context.date_end:
        return None
    normalized = normalize_text(text)
    if has_any(normalized, ["hoy", "ayer", "semana", "mes", "ano", "year"]) or any(char.isdigit() for char in normalized):
        return None
    if not _is_follow_up(normalized):
        return None
    return DateRange(context.date_start, context.date_end, context.date_label or "periodo anterior")


def context_summary(user_id: str, max_rows: int = 12) -> str:
    context = load_result_context(user_id)
    if not context:
        return ""
    parts = [
        f"Dominio: {context.domain}",
        f"Tipo de consulta: {context.intent}",
        f"Titulo: {context.title}",
    ]
    if context.date_start and context.date_end:
        parts.append(f"Periodo: {context.date_start} a {context.date_end} ({context.date_label})")
    if context.branch:
        parts.append(f"Sucursal: {context.branch}")
    if context.reference:
        parts.append(f"Referencia: {context.reference}")
    if context.focus_entity:
        parts.append(f"Entidad enfocada: {context.focus_entity} ({context.focus_label})")
    if not context.dataframe.empty:
        parts.append("Datos recientes:\n" + context.dataframe.head(max_rows).to_csv(index=False))
    return "\n".join(parts)


def _ensure_table() -> None:
    conn = connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS maria_conversation_context (
                user_id TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                intent TEXT NOT NULL,
                title TEXT,
                answer_text TEXT,
                result_json TEXT NOT NULL DEFAULT '[]',
                date_start TEXT,
                date_end TEXT,
                date_label TEXT,
                branch TEXT,
                reference TEXT,
                focus_entity TEXT,
                focus_label TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _set_focus(user_id: str, entity: str, label: str) -> None:
    conn = connect()
    try:
        conn.execute(
            """
            UPDATE maria_conversation_context
            SET focus_entity = ?, focus_label = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (entity, label, datetime.now().isoformat(timespec="seconds"), user_id or "anonymous"),
        )
        conn.commit()
    finally:
        conn.close()


def _is_follow_up(normalized: str) -> bool:
    return has_any(
        normalized,
        [
            "plan",
            "analiza",
            "analisis",
            "recomend",
            "accion",
            "estrateg",
            "mejor",
            "peor",
            "anterior",
            "resultado",
            "esa ",
            "ese ",
            "la sucursal",
            "compar",
        ],
    )


def _has_domain(normalized: str) -> bool:
    return has_any(
        normalized,
        [
            "venta",
            "ventas",
            "facturacion",
            "inventario",
            "existencia",
            "stock",
            "cliente",
            "presupuesto",
        ],
    )


def _uses_context_reference(normalized: str) -> bool:
    return has_any(
        normalized,
        [
            "esa sucursal",
            "ese resultado",
            "la anterior",
            "lo anterior",
            "analiza esa",
            "comparala",
            "plan para ella",
        ],
    )


def _metric_column(df: pd.DataFrame) -> str | None:
    for column in ["VentaNetaQ", "Venta", "MargenQ", "Margen", "ExistenciaFisica", "Existencia"]:
        if column in df.columns:
            return column
    return None


def _label_column(df: pd.DataFrame) -> str | None:
    for column in ["Sucursal", "Vendedor", "Cliente", "Referencia", "Linea", "CodEmbarqueAbreviado"]:
        if column in df.columns:
            return column
    return None


def _format_value(metric: str, value) -> str:
    number = float(value or 0)
    if metric in {"VentaNetaQ", "Venta", "MargenQ", "Margen"}:
        return f"Q {number:,.2f}"
    return f"{number:,.0f}"
