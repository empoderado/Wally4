from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from services import db


def date_sidebar() -> tuple[date, date]:
    try:
        min_date, max_date = db.min_max_date()
        default_day = db.default_sales_date()
    except Exception:
        max_date = date.today()
        min_date = max_date - timedelta(days=30)
        default_day = max_date

    default_day = min(max(default_day, min_date), max_date)
    st.sidebar.markdown("### Filtros")
    quick = st.sidebar.selectbox(
        "Periodo rápido",
        ["Hoy", "Ayer", "Últimos 7 días", "Últimos 30 días", "Mes actual", "Personalizado"],
        index=0,
    )

    if quick == "Hoy":
        default_start = default_day
        default_end = default_day
    elif quick == "Ayer":
        default_start = max(min_date, default_day - timedelta(days=1))
        default_end = default_start
    elif quick == "Últimos 7 días":
        default_start = max(min_date, default_day - timedelta(days=6))
        default_end = default_day
    elif quick == "Últimos 30 días":
        default_start = max(min_date, default_day - timedelta(days=29))
        default_end = default_day
    elif quick == "Mes actual":
        default_start = max(min_date, default_day.replace(day=1))
        default_end = default_day
    else:
        default_start = default_day
        default_end = default_day

    start = st.sidebar.date_input("Fecha Inicio", value=default_start, min_value=min_date, max_value=max_date)
    end = st.sidebar.date_input("Fecha Fin", value=default_end, min_value=min_date, max_value=max_date)
    if start > end:
        st.sidebar.error("La fecha inicio no puede ser mayor que la fecha fin.")
        return end, start
    return start, end


def optional_multiselect(label: str, options: list[str], format_func=None) -> list[str]:
    if not options:
        return []
    if format_func is not None:
        return st.sidebar.multiselect(label, options=options, default=[], format_func=format_func)
    return st.sidebar.multiselect(label, options=options, default=[])
