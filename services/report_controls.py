from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from services.charts import WALLY_COLORS, apply_chart_theme, horizontal_bar_layout


CHART_TYPES = ["Barras horizontales", "Barras verticales", "Línea", "Dona", "Dispersión"]


def color_picker(label: str = "Color principal", default: str = WALLY_COLORS[0]) -> str:
    return st.sidebar.color_picker(label, default)


def top_n_control(default: int = 15, max_value: int = 100) -> int:
    return int(st.sidebar.slider("Cantidad de registros en grafico", 5, max_value, default))


def metric_control(options: list[str], default: str) -> str:
    index = options.index(default) if default in options else 0
    return st.sidebar.selectbox("Metrica del grafico", options, index=index)


def chart_type_control(default: str = "Barras verticales", allowed: list[str] | None = None) -> str:
    options = allowed or CHART_TYPES
    index = options.index(default) if default in options else 0
    return st.sidebar.selectbox("Tipo de grafico", options, index=index)


def dimension_control(options: list[str], default: str) -> str:
    index = options.index(default) if default in options else 0
    return st.sidebar.selectbox("Agrupar por", options, index=index)


def aggregate_for_chart(df: pd.DataFrame, dimension: str, metric: str, top_n: int) -> pd.DataFrame:
    if df.empty or dimension not in df.columns or metric not in df.columns:
        return pd.DataFrame(columns=[dimension, metric])
    chart_df = (
        df.groupby(dimension, dropna=False, as_index=False)[metric]
        .sum()
        .sort_values(metric, ascending=False)
        .head(top_n)
    )
    chart_df[dimension] = chart_df[dimension].fillna("Sin dato").astype(str)
    return chart_df


def render_custom_chart(
    df: pd.DataFrame,
    dimension: str,
    metric: str,
    chart_type: str,
    color: str,
    top_n: int = 15,
    height: int = 390,
):
    chart_df = aggregate_for_chart(df, dimension, metric, top_n)
    if chart_df.empty:
        st.info("No hay datos para graficar.")
        return None

    if chart_type == "Barras horizontales":
        plot_df = chart_df.sort_values(metric, ascending=True)
        fig = px.bar(plot_df, x=metric, y=dimension, orientation="h", text=metric, color_discrete_sequence=[color])
        fig.update_traces(texttemplate="%{text:,.0f}")
        fig = horizontal_bar_layout(fig, height)
    elif chart_type == "Barras verticales":
        fig = px.bar(chart_df, x=dimension, y=metric, text=metric, color_discrete_sequence=[color])
        fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
        fig = apply_chart_theme(fig, height)
    elif chart_type == "Línea":
        fig = px.line(chart_df, x=dimension, y=metric, markers=True, color_discrete_sequence=[color])
        fig.update_traces(line=dict(width=3), marker=dict(size=7))
        fig = apply_chart_theme(fig, height)
    elif chart_type == "Dona":
        fig = px.pie(chart_df, names=dimension, values=metric, hole=.55, color_discrete_sequence=WALLY_COLORS)
        fig = apply_chart_theme(fig, height)
    else:
        fig = px.scatter(chart_df, x=dimension, y=metric, size=metric, color_discrete_sequence=[color])
        fig = apply_chart_theme(fig, height)

    st.plotly_chart(fig, use_container_width=True)
    return fig
