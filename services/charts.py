from __future__ import annotations

import plotly.graph_objects as go


WALLY_COLORS = [
    "#1f5eff",
    "#0f766e",
    "#b7791f",
    "#7c3aed",
    "#d92d20",
    "#334155",
    "#0891b2",
    "#16a34a",
]


def apply_chart_theme(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(family="Arial", color="#0f172a", size=12),
        margin=dict(l=12, r=12, t=16, b=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hoverlabel=dict(bgcolor="#0f172a", font_color="#ffffff", font_size=12),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor="#e2e8f0", tickfont=dict(size=11))
    fig.update_yaxes(showgrid=True, gridcolor="#edf2f7", zeroline=False, linecolor="#e2e8f0", tickfont=dict(size=11))
    return fig


def horizontal_bar_layout(fig: go.Figure, height: int = 390) -> go.Figure:
    apply_chart_theme(fig, height)
    fig.update_layout(yaxis=dict(autorange="reversed"))
    fig.update_traces(marker_line_width=0, textposition="outside", cliponaxis=False)
    return fig
