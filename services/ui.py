from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st
from datetime import datetime

from services import db


def page_title(title: str, subtitle: str = "") -> None:
    safe_title = escape(title)
    safe_subtitle = escape(subtitle)
    left, right = st.columns([0.82, 0.18], vertical_alignment="center")
    with left:
        st.markdown(
            f"""
            <div class="wally-page-heading">
                <div class="wally-eyebrow">Wally4</div>
                <h1>{safe_title}</h1>
                <div class="wally-subtitle">{safe_subtitle}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        if st.button("Actualizar", key=f"refresh_{title}", use_container_width=True):
            st.rerun()


def metric_card(label: str, value: str, delta: str = "", positive: bool | None = None) -> None:
    cls = "wally-muted"
    accent = "neutral"
    if positive is True:
        cls = "wally-good"
        accent = "good"
    elif positive is False:
        cls = "wally-bad"
        accent = "bad"
    safe_label = escape(str(label))
    safe_value = escape(str(value))
    safe_delta = escape(str(delta))
    st.markdown(
        f"""
        <div class="wally-card wally-card-{accent}">
            <div class="wally-label">{safe_label}</div>
            <div class="wally-value">{safe_value}</div>
            <div class="wally-delta {cls}">{safe_delta}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_footer(view_name: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    source = db.data_source_label()
    st.markdown(
        f"""
        <div class="wally-page-footer">
            <strong>Vista utilizada:</strong> {view_name} |
            <strong>Origen de datos:</strong> {source} |
            <strong>Ultima actualizacion del dashboard:</strong> {stamp}.<br>
            Los valores incluyen impuestos y todos los reportes responden al rango de fechas y filtros seleccionados.
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(title: str) -> None:
    st.markdown(f'<div class="wally-section-title">{escape(title)}</div>', unsafe_allow_html=True)


def warning_box(text: str) -> None:
    st.markdown(f'<div class="wally-alert">{escape(text)}</div>', unsafe_allow_html=True)


def chart_panel(title: str) -> None:
    section_title(title)


def code_footer(code: str, description: str) -> None:
    st.markdown(
        f"""
        <div class="wally-code-footer">
            <span>Codigo: {escape(code)}</span>
            <small>{escape(description)}</small>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _is_totalizable_column(column: str, series: pd.Series) -> bool:
    lower = column.lower()
    if lower in {"ranking", "rank"}:
        return False
    if "%" in column or "porc" in lower or lower == "upt" or "factprom" in lower or "promedio" in lower:
        return False
    return pd.api.types.is_numeric_dtype(series)


def add_total_row(df: pd.DataFrame, label: str = "Total") -> pd.DataFrame:
    if df.empty:
        return df
    data = df.copy()
    total = {}
    first_text_column = None
    for col in data.columns:
        if _is_totalizable_column(col, data[col]):
            total[col] = data[col].sum()
        else:
            total[col] = ""
            if first_text_column is None:
                first_text_column = col
    if first_text_column:
        total[first_text_column] = label
    else:
        total[data.columns[0]] = label
    return pd.concat([data, pd.DataFrame([total])], ignore_index=True)


def _highlight_total(row):
    is_total = any(str(value).strip().lower() == "total" for value in row)
    if is_total:
        return ["background-color: #fff7ed; color: #7c2d12; font-weight: 800;" for _ in row]
    return ["" for _ in row]


def _highlight_zero_stock(value):
    if pd.isna(value) or value == "":
        return ""
    try:
        if float(str(value).replace("Q", "").replace(".", "").replace(",", ".").strip()) == 0:
            return "background-color: #ffe4e6; color: #9f1239; font-weight: 700;"
    except Exception:
        return ""
    return ""


def _format_value(value, column: str) -> str:
    if pd.isna(value) or value == "":
        return ""
    lower = column.lower()
    try:
        number_value = float(value)
    except Exception:
        return str(value)

    if lower in {"ranking", "rank"}:
        return f"{number_value:,.0f}".replace(",", ".")
    if lower == "upt":
        return f"{number_value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if lower in {"factprom", "vrpromediounidad"}:
        return f"Q {number_value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if "%" in column or "porc" in lower:
        return f"{number_value * 100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
    if any(token in lower for token in ("venta", "costo", "margen", "descuento", "meta", "ticket", "factprom", "vrpromedio", "vr unidad")):
        return f"Q {number_value:,.0f}".replace(",", ".")
    if number_value.is_integer():
        return f"{number_value:,.0f}".replace(",", ".")
    return f"{number_value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _format_table_values(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    for col in formatted.columns:
        formatted[col] = formatted[col].map(lambda value, column=col: _format_value(value, column))
    return formatted


def display_table(
    df: pd.DataFrame,
    height: int = 430,
    show_total: bool = True,
    highlight_zero_columns: list[str] | None = None,
) -> None:
    data = add_total_row(df) if show_total else df
    numeric_columns = [col for col in data.columns if pd.api.types.is_numeric_dtype(data[col])]
    formatted = _format_table_values(data)
    styler = formatted.style.apply(_highlight_total, axis=1)
    for col in highlight_zero_columns or []:
        if col in formatted.columns:
            styler = styler.applymap(_highlight_zero_stock, subset=[col])
    if numeric_columns:
        styler = styler.set_properties(subset=numeric_columns, **{"text-align": "right"})
    st.dataframe(styler, use_container_width=True, hide_index=True, height=height)


def display_compact_table(df: pd.DataFrame, show_total: bool = True) -> None:
    data = add_total_row(df) if show_total else df
    formatted = _format_table_values(data)
    styler = (
        formatted.style
        .apply(_highlight_total, axis=1)
        .set_table_styles(
            [
                {"selector": "table", "props": [("width", "auto"), ("border-collapse", "collapse")]},
                {"selector": "th", "props": [("text-align", "left"), ("padding", "7px 10px"), ("white-space", "nowrap")]},
                {"selector": "td", "props": [("padding", "7px 10px"), ("white-space", "nowrap")]},
            ]
        )
    )
    st.markdown(styler.to_html(index=False), unsafe_allow_html=True)


def filter_dataframe(df: pd.DataFrame, key_prefix: str, columns: list[str] | None = None) -> pd.DataFrame:
    if df.empty:
        return df
    selected_columns = columns or list(df.columns)
    with st.expander("Filtros de tabla", expanded=False):
        filtered = df.copy()
        cols = st.columns(3)
        for idx, col in enumerate(selected_columns):
            if col not in filtered.columns:
                continue
            with cols[idx % 3]:
                value = st.text_input(f"Filtrar {col}", key=f"{key_prefix}_{col}")
            if value:
                filtered = filtered[filtered[col].astype(str).str.contains(value, case=False, na=False)]
    return filtered

