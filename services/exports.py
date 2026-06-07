from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from services.paths import APP_DIR


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


def _configure_logger() -> None:
    if LOGGER.handlers:
        return
    try:
        log_dir = APP_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_dir / "exports.log", encoding="utf-8")
    except Exception:
        handler = logging.NullHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOGGER.addHandler(handler)


def _safe_sheet_name(sheet_name: Any, fallback_index: int) -> str:
    text = str(sheet_name or f"Datos {fallback_index}").strip() or f"Datos {fallback_index}"
    for char in (":", "\\", "/", "?", "*", "[", "]"):
        text = text.replace(char, "-")
    return text[:31] or f"Datos {fallback_index}"


def _normalize_dataframe(sheet_name: str, value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        df = value.copy()
    elif isinstance(value, pd.Series):
        LOGGER.warning("Excel export sheet '%s' received a Series; converting to DataFrame.", sheet_name)
        df = value.to_frame()
    elif value is None:
        LOGGER.warning("Excel export sheet '%s' received None; exporting an empty sheet.", sheet_name)
        df = pd.DataFrame()
    elif isinstance(value, (str, bytes, int, float, bool)):
        LOGGER.warning("Excel export sheet '%s' received scalar %r; wrapping in a DataFrame.", sheet_name, value)
        df = pd.DataFrame({"Valor": [value]})
    else:
        try:
            df = pd.DataFrame(value)
            LOGGER.warning("Excel export sheet '%s' received %s; converted to DataFrame.", sheet_name, type(value).__name__)
        except Exception:
            LOGGER.exception("Excel export sheet '%s' has invalid structure; exporting an error sheet.", sheet_name)
            df = pd.DataFrame({"Error": [f"Estructura invalida para exportar: {type(value).__name__}"]})

    if not isinstance(df.columns, pd.Index):
        LOGGER.warning("Excel export sheet '%s' has invalid columns object %r; resetting columns.", sheet_name, df.columns)
        df.columns = pd.RangeIndex(start=0, stop=len(df.columns), step=1)

    if df.columns.has_duplicates:
        LOGGER.warning("Excel export sheet '%s' has duplicate columns; making names unique.", sheet_name)
        df.columns = _unique_columns(df.columns)

    return df


def _unique_columns(columns: pd.Index) -> list[str]:
    seen: dict[str, int] = {}
    unique: list[str] = []
    for column in columns:
        base = str(column) if str(column).strip() else "Columna"
        count = seen.get(base, 0)
        seen[base] = count + 1
        unique.append(base if count == 0 else f"{base}_{count + 1}")
    return unique


def _safe_column_values(df: pd.DataFrame, column: Any, sheet_name: str) -> list[Any]:
    if column not in df.columns:
        LOGGER.warning("Excel export sheet '%s' missing column %r while sizing; using header only.", sheet_name, column)
        return []
    try:
        values = df.loc[:, column]
    except Exception:
        LOGGER.exception("Excel export sheet '%s' could not read column %r while sizing.", sheet_name, column)
        return []
    if isinstance(values, pd.DataFrame):
        LOGGER.warning("Excel export sheet '%s' column %r resolved to DataFrame; flattening values.", sheet_name, column)
        flattened = values.head(200).fillna("").astype(str).to_numpy().ravel().tolist()
        return flattened
    if not isinstance(values, pd.Series):
        LOGGER.warning("Excel export sheet '%s' column %r resolved to scalar %r; wrapping value.", sheet_name, column, values)
        return [values]
    try:
        return values.head(200).fillna("").tolist()
    except Exception:
        LOGGER.exception("Excel export sheet '%s' could not iterate values for column %r.", sheet_name, column)
        return []


def _column_width(df: pd.DataFrame, column: Any, sheet_name: str) -> int:
    lengths = [len(str(column))]
    for item in _safe_column_values(df, column, sheet_name):
        try:
            lengths.append(len(str(item)))
        except Exception:
            LOGGER.exception("Excel export sheet '%s' failed converting value in column %r.", sheet_name, column)
    return max(10, min(34, max(lengths or [10]) + 2))


@st.cache_data(ttl=300, max_entries=32, show_spinner=False)
def dataframe_to_excel_bytes(sheets: dict[str, Any] | Any) -> bytes:
    _configure_logger()
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        if not isinstance(sheets, dict):
            LOGGER.warning("Excel export received non-dict sheets object %s; wrapping it.", type(sheets).__name__)
            sheets = {"Datos": sheets}
        if not sheets:
            LOGGER.warning("Excel export received no sheets; exporting an empty sheet.")
            sheets = {"Datos": pd.DataFrame()}
        used_names: set[str] = set()
        for index, (sheet_name, sheet_value) in enumerate(sheets.items(), start=1):
            safe_name = _safe_sheet_name(sheet_name, index)
            while safe_name in used_names:
                suffix = f"_{index}"
                safe_name = f"{safe_name[:31 - len(suffix)]}{suffix}"
            used_names.add(safe_name)
            df = _normalize_dataframe(safe_name, sheet_value)
            df.to_excel(writer, index=False, sheet_name=safe_name)
            workbook = writer.book
            worksheet = writer.sheets[safe_name]
            header_fmt = workbook.add_format({"bold": True, "bg_color": "#17365D", "font_color": "#FFFFFF"})
            for col_num, column in enumerate(df.columns.tolist()):
                worksheet.write(0, col_num, str(column), header_fmt)
                width = _column_width(df, column, safe_name)
                worksheet.set_column(col_num, col_num, width)
            worksheet.freeze_panes(1, 0)
            if len(df.columns) > 0:
                worksheet.autofilter(0, 0, max(len(df), 1), len(df.columns) - 1)
    return output.getvalue()


def export_filename(prefix: str, extension: str = "xlsx") -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}.{extension}"
