from __future__ import annotations

import re
from dataclasses import dataclass

from agents.intent_router import normalize_text


KNOWN_BRANCHES = {
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


@dataclass(frozen=True)
class QueryContext:
    branch: str | None = None
    reference: str | None = None
    limit: int = 10


def parse_query_context(text: str) -> QueryContext:
    normalized = normalize_text(text)
    return QueryContext(
        branch=extract_branch(normalized),
        reference=extract_reference(text),
        limit=extract_limit(normalized),
    )


def extract_branch(normalized_text: str) -> str | None:
    matches = [
        branch
        for key, branch in KNOWN_BRANCHES.items()
        if key in normalized_text
    ]
    if not matches:
        return None
    return max(matches, key=len)


def extract_reference(text: str) -> str | None:
    candidates = re.findall(r"\b[A-Z]{1,4}\d{4,8}[A-Z0-9]{0,4}\b", text.upper())
    if not candidates:
        return None
    return max(candidates, key=len)


def extract_limit(normalized_text: str) -> int:
    match = re.search(r"\btop\s+(\d{1,2})\b", normalized_text)
    if match:
        return max(1, min(int(match.group(1)), 25))
    match = re.search(r"\b(\d{1,2})\s+(primeros|principales|mayores)\b", normalized_text)
    if match:
        return max(1, min(int(match.group(1)), 25))
    return 10
