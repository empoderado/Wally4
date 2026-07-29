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
        font=dict(family="Arial", color="#0f172a", size=11),
        margin=dict(l=75, r=20, t=35, b=45),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hoverlabel=dict(bgcolor="#0f172a", font_color="#ffffff", font_size=11),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor="#e2e8f0", tickfont=dict(size=9))
    fig.update_yaxes(showgrid=True, gridcolor="#edf2f7", zeroline=False, linecolor="#e2e8f0", tickfont=dict(size=9))
    return fig


def horizontal_bar_layout(fig: go.Figure, height: int = 390) -> go.Figure:
    apply_chart_theme(fig, height)
    fig.update_layout(yaxis=dict(autorange="reversed"))
    fig.update_traces(marker_line_width=0, textposition="outside", cliponaxis=False)
    return fig


def build_branch_chart(df: pd.DataFrame, height: int = 300) -> go.Figure:
    import pandas as pd
    # Filter out total rows (both 'total' and 'total acumulado')
    df_clean = df[~df["Sucursal"].astype(str).str.lower().str.strip().isin(["total", "total acumulado"])].copy()
    df_clean = df_clean.sort_values(by="VentaNetaQ", ascending=False)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_clean["Sucursal"],
        y=df_clean["VentaNetaQ"],
        text=df_clean["VentaNetaQ"].apply(lambda v: f"Q {v:,.0f}" if pd.notna(v) and v != "" else ""),
        textposition="outside",
        marker_color="#6c1c36",
        name="Venta Neta"
    ))
    
    apply_chart_theme(fig, height=height)
    fig.update_layout(
        margin=dict(l=75, r=20, t=35, b=45),
        xaxis_title=None,
        yaxis_title=None,
        showlegend=False
    )
    fig.update_yaxes(tickprefix="Q ", tickformat=",")
    
    # Expand Y range to prevent text values at the top of the bars from being cut off
    max_val = df_clean["VentaNetaQ"].max() if not df_clean.empty else 0
    if max_val:
        fig.update_yaxes(range=[0, max_val * 1.15])
        
    return fig


def build_line_chart(df: pd.DataFrame, height: int = 300) -> go.Figure:
    import pandas as pd
    df_clean = df[~df["Linea"].astype(str).str.lower().str.strip().isin(["total", "total acumulado"])].copy()
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_clean["Linea"],
        y=df_clean["VentaQ"],
        name="Venta Real",
        marker_color="#6c1c36",
        text=df_clean["VentaQ"].apply(lambda v: f"Q {v:,.0f}" if pd.notna(v) and v != "" else ""),
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        x=df_clean["Linea"],
        y=df_clean["PresupuestoVenta"],
        name="Presupuesto",
        marker_color="#94a3b8",
        text=df_clean["PresupuestoVenta"].apply(lambda v: f"Q {v:,.0f}" if pd.notna(v) and v != "" else ""),
        textposition="outside",
    ))
    
    apply_chart_theme(fig, height=height)
    fig.update_layout(
        barmode="group",
        margin=dict(l=75, r=20, t=35, b=45),
        xaxis_title=None,
        yaxis_title=None,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_yaxes(tickprefix="Q ", tickformat=",")
    
    # Expand Y range to prevent text values at the top of the bars from being cut off
    max_val = max(df_clean["VentaQ"].max(), df_clean["PresupuestoVenta"].max()) if not df_clean.empty else 0
    if max_val:
        fig.update_yaxes(range=[0, max_val * 1.15])
        
    return fig


def build_daily_chart(df: pd.DataFrame, years: dict[str, int] = None, height: int = 300) -> go.Figure:
    import pandas as pd
    df_clean = df[~df["Dia"].astype(str).str.lower().str.strip().isin(["total", "total acumulado"])].copy()
    
    try:
        df_clean["Dia_num"] = pd.to_numeric(df_clean["Dia"])
        df_clean = df_clean.sort_values(by="Dia_num")
    except Exception:
        pass
        
    y_previous = str(years.get("previous", "2025")) if years else "Año Anterior"
    y_current = str(years.get("current", "2026")) if years else "Hoy"
    
    fig = go.Figure()
    
    if "PromHistoricoVentaNeta" in df_clean.columns:
        fig.add_trace(go.Scatter(
            x=df_clean["Dia"],
            y=df_clean["PromHistoricoVentaNeta"],
            name="Promedio Histórico",
            line=dict(color="#475569", width=2, dash="dash"),
            mode="lines+markers"
        ))
        
    if "AnioAnteriorVentaNeta" in df_clean.columns:
        fig.add_trace(go.Scatter(
            x=df_clean["Dia"],
            y=df_clean["AnioAnteriorVentaNeta"],
            name=f"Año Anterior ({y_previous})",
            line=dict(color="#3b82f6", width=2),
            mode="lines+markers"
        ))
        
    if "HoyVentaNeta" in df_clean.columns:
        fig.add_trace(go.Scatter(
            x=df_clean["Dia"],
            y=df_clean["HoyVentaNeta"],
            name=f"Venta Actual ({y_current})",
            line=dict(color="#6c1c36", width=3.5),
            mode="lines+markers"
        ))
        
    apply_chart_theme(fig, height=height)
    fig.update_layout(
        margin=dict(l=75, r=20, t=35, b=45),
        xaxis_title="Día",
        yaxis_title=None,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_yaxes(tickprefix="Q ", tickformat=",")
    
    # Expand Y range slightly to prevent line markers at peaks from being cut off
    all_vals = []
    for col in ["HoyVentaNeta", "AnioAnteriorVentaNeta", "PromHistoricoVentaNeta"]:
        if col in df_clean.columns:
            all_vals.extend(df_clean[col].dropna().tolist())
    max_val = max(all_vals) if all_vals else 0
    if max_val:
        fig.update_yaxes(range=[0, max_val * 1.10])
        
    return fig

