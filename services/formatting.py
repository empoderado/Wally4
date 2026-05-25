from __future__ import annotations

from decimal import Decimal

import pandas as pd


def as_float(value: float | int | Decimal | None) -> float:
    if value is None or pd.isna(value):
        return 0.0
    return float(value)


def money(value: float | int | Decimal | None) -> str:
    return f"Q {as_float(value):,.0f}".replace(",", ".")


def number(value: float | int | Decimal | None, decimals: int = 0) -> str:
    fmt = f"{{:,.{decimals}f}}"
    return fmt.format(as_float(value)).replace(",", "X").replace(".", ",").replace("X", ".")


def percent(value: float | int | Decimal | None) -> str:
    return f"{as_float(value) * 100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def compact_table(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    for col in formatted.columns:
        lower = col.lower()
        if formatted[col].dtype.kind in {"f", "i"}:
            if "porcentaje" in lower or lower.startswith("%") or lower.endswith("pct"):
                formatted[col] = formatted[col].map(lambda x: percent(x))
            elif any(token in lower for token in ("venta", "costo", "margen", "descuento", "meta", "ticket")):
                formatted[col] = formatted[col].map(lambda x: money(x))
            elif formatted[col].dtype.kind == "f":
                formatted[col] = formatted[col].map(lambda x: number(x, 2))
            else:
                formatted[col] = formatted[col].map(lambda x: number(x, 0))
    return formatted
