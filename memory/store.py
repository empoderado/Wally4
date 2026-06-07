from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re

import pandas as pd

from services.local_store import connect
from agents.intent_router import normalize_text


@dataclass(frozen=True)
class MemorySnapshot:
    short_term: pd.DataFrame
    medium_term: pd.DataFrame
    permanent: pd.DataFrame


def log_conversation(
    *,
    channel: str,
    user_id: str,
    user_name: str,
    question: str,
    answer: str,
    intent: str,
) -> None:
    conn = connect()
    try:
        conn.execute(
            """
            INSERT INTO maria_conversations
                (channel, user_id, user_name, question, answer, intent, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                channel,
                user_id,
                user_name,
                question,
                answer,
                intent,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def recent_conversations(limit: int = 10, user_id: str | None = None) -> pd.DataFrame:
    conn = connect()
    try:
        if user_id:
            return pd.read_sql_query(
                """
                SELECT created_at, channel, user_name, question, answer, intent
                FROM maria_conversations
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                conn,
                params=(user_id, limit),
            )
        return pd.read_sql_query(
            """
            SELECT created_at, channel, user_name, question, answer, intent
            FROM maria_conversations
            ORDER BY id DESC
            LIMIT ?
            """,
            conn,
            params=(limit,),
        )
    finally:
        conn.close()


def active_memories(memory_type: str | None = None, user_id: str | None = None) -> pd.DataFrame:
    cleanup_expired_memories()
    filters = ["(expires_at IS NULL OR expires_at >= ?)"]
    params: list = [datetime.now().isoformat(timespec="seconds")]
    if memory_type:
        filters.append("memory_type = ?")
        params.append(memory_type)
    if user_id:
        filters.append("(user_id = ? OR user_id IS NULL OR user_id = '')")
        params.append(user_id)

    conn = connect()
    try:
        return pd.read_sql_query(
            f"""
            SELECT memory_type, key_text, value_text, user_id, expires_at, created_at
            FROM maria_memory
            WHERE {" AND ".join(filters)}
            ORDER BY created_at DESC
            """,
            conn,
            params=params,
        )
    finally:
        conn.close()


def memory_snapshot(user_id: str | None = None) -> MemorySnapshot:
    return MemorySnapshot(
        short_term=recent_conversations(limit=12, user_id=user_id),
        medium_term=active_memories("medium", user_id=user_id),
        permanent=active_memories("permanent", user_id=user_id),
    )


def memory_summary(user_id: str | None = None) -> str:
    memories = active_memories(user_id=user_id)
    if memories.empty:
        return ""
    lines = []
    for _, row in memories.head(20).iterrows():
        lines.append(f"{row['key_text']}: {row['value_text']} ({row['memory_type']})")
    return "\n".join(lines)


def remember(
    *,
    memory_type: str,
    key_text: str,
    value_text: str,
    user_id: str = "",
    days: int | None = None,
) -> None:
    if memory_type not in {"medium", "permanent"}:
        raise ValueError("memory_type debe ser medium o permanent")
    now = datetime.now()
    expires_at = None if memory_type == "permanent" else (now + timedelta(days=days or 90)).isoformat(timespec="seconds")
    conn = connect()
    try:
        conn.execute(
            """
            INSERT INTO maria_memory (memory_type, key_text, value_text, user_id, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                memory_type,
                key_text.strip(),
                value_text.strip(),
                user_id,
                expires_at,
                now.isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def cleanup_expired_memories() -> None:
    conn = connect()
    try:
        conn.execute(
            "DELETE FROM maria_memory WHERE expires_at IS NOT NULL AND expires_at < ?",
            (datetime.now().isoformat(timespec="seconds"),),
        )
        conn.commit()
    finally:
        conn.close()


def try_capture_memory(text: str, user_id: str = "") -> str | None:
    normalized = normalize_text(text)
    if not (
        normalized.startswith("recuerda que")
        or normalized.startswith("recuerda siempre que")
        or normalized.startswith("recuerda permanentemente que")
        or normalized.startswith("recordar que")
        or normalized.startswith("ten presente")
        or normalized.startswith("ten en cuenta")
    ):
        return None

    branch = _extract_branch_memory(normalized)
    memory_type = "permanent" if any(term in normalized for term in ["siempre", "permanente", "de ahora en adelante"]) else "medium"
    days = 365 if memory_type == "medium" else None

    if branch:
        remember(
            memory_type=memory_type,
            key_text="preferred_branch",
            value_text=branch,
            user_id=user_id,
            days=days,
        )
        label = "permanente" if memory_type == "permanent" else "de mediano plazo"
        return f"Listo. Recordare como memoria {label} que tu sucursal principal es **{branch}**."

    raw = re.sub(r"(?i)^(recuerda que|recordar que|ten presente que|ten en cuenta que)\s*", "", text).strip()
    if raw:
        remember(
            memory_type=memory_type,
            key_text="user_note",
            value_text=raw,
            user_id=user_id,
            days=days,
        )
        label = "permanente" if memory_type == "permanent" else "de mediano plazo"
        return f"Listo. Guarde esa nota como memoria {label}."
    return None


def apply_memory_to_question(text: str, user_id: str = "") -> str:
    normalized = normalize_text(text)
    if not any(term in normalized for term in ["mi sucursal", "sucursal principal", "sucursal preferida"]):
        return text
    branch = get_memory_value("preferred_branch", user_id=user_id)
    if not branch:
        return text
    enriched = text
    for phrase in ["mi sucursal principal", "mi sucursal preferida", "mi sucursal"]:
        enriched = re.sub(phrase, branch, enriched, flags=re.IGNORECASE)
    return enriched


def get_memory_value(key_text: str, user_id: str = "") -> str | None:
    cleanup_expired_memories()
    conn = connect()
    try:
        row = conn.execute(
            """
            SELECT value_text
            FROM maria_memory
            WHERE key_text = ?
              AND (user_id = ? OR user_id IS NULL OR user_id = '')
              AND (expires_at IS NULL OR expires_at >= ?)
            ORDER BY
              CASE WHEN user_id = ? THEN 0 ELSE 1 END,
              created_at DESC
            LIMIT 1
            """,
            (key_text, user_id, datetime.now().isoformat(timespec="seconds"), user_id),
        ).fetchone()
        return row["value_text"] if row else None
    finally:
        conn.close()


def answer_memory_question(text: str, user_id: str = "") -> str | None:
    normalized = normalize_text(text)
    asks_memory = any(term in normalized for term in ["que recuerdas", "que sabes de mi", "recuerdas de mi"])
    asks_branch_memory = "sucursal" in normalized and any(term in normalized for term in ["cual es", "que es", "cual tengo"])
    if not asks_memory and not asks_branch_memory:
        return None
    if asks_branch_memory:
        branch = get_memory_value("preferred_branch", user_id=user_id)
        if branch:
            return f"Recuerdo que tu sucursal principal es **{branch}**."
    snapshot = memory_snapshot(user_id=user_id)
    medium_count = len(snapshot.medium_term)
    permanent_count = len(snapshot.permanent)
    short_count = len(snapshot.short_term)
    return (
        "**Memoria activa de Mar-IA**\n\n"
        f"1. Corto plazo: {short_count} conversaciones recientes.\n\n"
        f"2. Mediano plazo: {medium_count} recuerdos activos con vencimiento.\n\n"
        f"3. Permanente: {permanent_count} recuerdos aprobados sin vencimiento."
    )


def _extract_branch_memory(normalized: str) -> str | None:
    branches = {
        "oakland": "OAKLAND",
        "chiquimula": "CHIQUIMULA",
        "pradera": "PRADERA",
        "americas": "AMERICAS",
        "parque las americas": "AMERICAS",
        "majadas": "MAJADAS",
        "naranjo": "NARANJO MALL",
        "naranjo mall": "NARANJO MALL",
        "escuintla": "ESCUINTLA",
        "online": "ON-LINE",
        "on-line": "ON-LINE",
        "basshert": "BASSHERT",
    }
    if not any(term in normalized for term in ["sucursal", "tienda"]):
        return None
    matches = [branch for key, branch in branches.items() if key in normalized]
    return max(matches, key=len) if matches else None
