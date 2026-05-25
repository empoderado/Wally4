from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from services.formatting import money, number


def _format_pct(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return '<span class="wally-var-na">-</span>'
    try:
        pct = float(value)
    except Exception:
        return '<span class="wally-var-na">-</span>'
    text = f"{pct:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
    if pct > 0:
        return f'<span class="wally-var-pos">&#9650; {text}</span>'
    if pct < 0:
        return f'<span class="wally-var-neg">&#9660; {text}</span>'
    return '<span class="wally-var-neu">0,00%</span>'


def _money(value: float | int | None) -> str:
    return escape(money(value))


def _usd(value: float | int | None) -> str:
    return escape(f"US$ {number(value)}")


def _num(value: float | int | None) -> str:
    if isinstance(value, str) and not value.strip():
        return ""
    return escape(number(value))


def mock_hourly_comparison_data() -> list[dict]:
    return [
        {
            "RangoHora": "8 - 9",
            "Historico2023Unid": 120,
            "Historico2023VentaNeta": 3500,
            "Historico2024Unid": 140,
            "Historico2024VentaNeta": 4100,
            "AnioAnteriorUnid": 155,
            "AnioAnteriorVentaNeta": 4850,
            "HoyUnid": 170,
            "HoyVentaNeta": 5300,
            "PromHistoricoUnid": 138.33,
            "PromHistoricoVentaNeta": 4150,
            "VariacionUnidPct": 9.68,
            "VariacionVentaPct": 9.28,
            "VariacionPromUnidPct": 22.89,
            "VariacionPromVentaPct": 27.71,
        }
    ]


def _append_total(rows: pd.DataFrame) -> pd.DataFrame:
    total = {
        "RangoHora": "Total Acumulado",
        "Historico2023Unid": rows["Historico2023Unid"].sum(),
        "Historico2023VentaNeta": rows["Historico2023VentaNeta"].sum(),
        "Historico2024Unid": rows["Historico2024Unid"].sum(),
        "Historico2024VentaNeta": rows["Historico2024VentaNeta"].sum(),
        "AnioAnteriorUnid": rows["AnioAnteriorUnid"].sum(),
        "AnioAnteriorVentaNeta": rows["AnioAnteriorVentaNeta"].sum(),
        "HoyUnid": rows["HoyUnid"].sum(),
        "HoyVentaNeta": rows["HoyVentaNeta"].sum(),
        "PromHistoricoUnid": rows["PromHistoricoUnid"].sum(),
        "PromHistoricoVentaNeta": rows["PromHistoricoVentaNeta"].sum(),
    }
    total["VariacionUnidPct"] = (
        ((total["HoyUnid"] - total["AnioAnteriorUnid"]) / total["AnioAnteriorUnid"]) * 100
        if total["AnioAnteriorUnid"]
        else 0
    )
    total["VariacionVentaPct"] = (
        ((total["HoyVentaNeta"] - total["AnioAnteriorVentaNeta"]) / total["AnioAnteriorVentaNeta"]) * 100
        if total["AnioAnteriorVentaNeta"]
        else 0
    )
    total["VariacionPromUnidPct"] = (
        ((total["HoyUnid"] - total["PromHistoricoUnid"]) / total["PromHistoricoUnid"]) * 100
        if total["PromHistoricoUnid"]
        else 0
    )
    total["VariacionPromVentaPct"] = (
        ((total["HoyVentaNeta"] - total["PromHistoricoVentaNeta"]) / total["PromHistoricoVentaNeta"]) * 100
        if total["PromHistoricoVentaNeta"]
        else 0
    )
    return pd.concat([rows, pd.DataFrame([total])], ignore_index=True)


def _row_html(row: pd.Series) -> str:
    row_class = "wally-total-row" if str(row["RangoHora"]) == "Total Acumulado" else ""
    return (
        f'<tr class="{row_class}">'
        f'<td class="wally-hour">{escape(str(row["RangoHora"]))}</td>'
        f'<td>{_num(row["Historico2023Unid"])}</td><td>{_money(row["Historico2023VentaNeta"])}</td>'
        f'<td>{_num(row["Historico2024Unid"])}</td><td>{_money(row["Historico2024VentaNeta"])}</td>'
        f'<td>{_num(row["AnioAnteriorUnid"])}</td><td>{_money(row["AnioAnteriorVentaNeta"])}</td>'
        f'<td>{_num(row["PromHistoricoUnid"])}</td><td>{_money(row["PromHistoricoVentaNeta"])}</td>'
        f'<td>{_num(row["HoyUnid"])}</td><td>{_money(row["HoyVentaNeta"])}</td>'
        f'<td>{_format_pct(row["VariacionUnidPct"])}</td><td>{_format_pct(row["VariacionVentaPct"])}</td>'
        f'<td>{_format_pct(row["VariacionPromUnidPct"])}</td><td>{_format_pct(row["VariacionPromVentaPct"])}</td>'
        "</tr>"
    )


def render_hourly_comparison_table(df: pd.DataFrame, years: dict[str, int]) -> None:
    if df.empty:
        st.info("No hay datos por hora para el rango consultado.")
        return

    rows = _append_total(df.copy())
    body_html = "".join(_row_html(row) for _, row in rows.iterrows())
    html = (
        "<style>"
        ".wally-hour-table-wrap{width:max-content;max-width:100%;overflow-x:auto;border:1px solid #d8dee8;border-radius:8px;background:#fff;box-shadow:0 2px 10px rgba(15,23,42,.045);margin-bottom:12px}"
        "table.wally-hour-table{width:auto;min-width:0;border-collapse:separate;border-spacing:0;font-size:.74rem;color:#0f172a;table-layout:auto}"
        ".wally-hour-table th,.wally-hour-table td{padding:6px 7px;border-right:1px solid #e2e8f0;border-bottom:1px solid #e2e8f0;white-space:nowrap;line-height:1.15}"
        ".wally-hour-table thead tr:first-child th{background:#0f1f33;color:#fff;text-align:center;font-weight:800;letter-spacing:0}"
        ".wally-hour-table thead tr:nth-child(2) th{color:#334155;text-align:center;font-weight:760}"
        ".wally-hour-table .head-hist{background:#edf2f7!important;color:#0f172a!important}"
        ".wally-hour-table .head-prev{background:#dbeafe!important;color:#1e3a8a!important}"
        ".wally-hour-table .head-prom{background:#fef3c7!important;color:#92400e!important}"
        ".wally-hour-table .head-today{background:#dcfce7!important;color:#14532d!important}"
        ".wally-hour-table .head-var{background:#f8fafc!important;color:#0f172a!important}"
        ".wally-hour-table td{text-align:right;background:#fff}"
        ".wally-hour-table th:not(:first-child),.wally-hour-table td:not(:first-child){min-width:64px;max-width:92px}"
        ".wally-hour-table td:nth-child(3),.wally-hour-table td:nth-child(5),.wally-hour-table td:nth-child(7),.wally-hour-table td:nth-child(9){min-width:78px;max-width:98px}"
        ".wally-hour-table .wally-hour{min-width:58px;max-width:70px;text-align:center;font-weight:720;color:#334155;background:#f8fafc;position:sticky;left:0;z-index:1}"
        ".wally-hour-table .wally-total-row td{background:#fff7ed;color:#7c2d12;font-weight:850}"
        ".wally-var-pos{color:#047857;font-weight:850}.wally-var-neg{color:#dc2626;font-weight:850}.wally-var-neu{color:#64748b;font-weight:850}.wally-var-na{color:#94a3b8;font-weight:850}"
        "</style>"
        '<div class="wally-hour-table-wrap"><table class="wally-hour-table"><thead>'
        "<tr>"
        '<th rowspan="2">Rango Hora</th>'
        f'<th class="head-hist" colspan="2">{years["hist_1"]}</th>'
        f'<th class="head-hist" colspan="2">{years["hist_2"]}</th>'
        f'<th class="head-prev" colspan="2">{years["previous"]}</th>'
        '<th class="head-prom" colspan="2">PromHistorico</th>'
        f'<th class="head-today" colspan="2">Hoy {years["current"]}</th>'
        f'<th class="head-var" colspan="2">Variaci&oacute;n vs {years["previous"]}</th>'
        '<th class="head-var" colspan="2">Variaci&oacute;n vs PromHistorico</th>'
        "</tr>"
        "<tr><th>Unid</th><th>Venta Neta</th><th>Unid</th><th>Venta Neta</th><th>Unid</th><th>Venta Neta</th><th>Unid</th><th>Venta Neta</th><th>Unid</th><th>Venta Neta</th><th>Unid %</th><th>Venta %</th><th>Unid %</th><th>Venta %</th></tr>"
        f"</thead><tbody>{body_html}</tbody></table></div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def mock_daily_comparison_data() -> list[dict]:
    return [
        {
            "Dia": 1,
            "Historico2023Unid": 120,
            "Historico2023VentaNeta": 3500,
            "Historico2024Unid": 140,
            "Historico2024VentaNeta": 4100,
            "AnioAnteriorUnid": 155,
            "AnioAnteriorVentaNeta": 4850,
            "PromHistoricoUnid": 138.33,
            "PromHistoricoVentaNeta": 4150,
            "HoyUnid": 170,
            "HoyVentaNeta": 5300,
            "VariacionUnidPct": 9.68,
            "VariacionVentaPct": 9.28,
            "VariacionPromUnidPct": 22.89,
            "VariacionPromVentaPct": 27.71,
        }
    ]


def _append_daily_total(rows: pd.DataFrame) -> pd.DataFrame:
    total = {
        "Dia": "Total acumulado",
        "Historico2023Unid": rows["Historico2023Unid"].sum(),
        "Historico2023VentaNeta": rows["Historico2023VentaNeta"].sum(),
        "Historico2024Unid": rows["Historico2024Unid"].sum(),
        "Historico2024VentaNeta": rows["Historico2024VentaNeta"].sum(),
        "AnioAnteriorUnid": rows["AnioAnteriorUnid"].sum(),
        "AnioAnteriorVentaNeta": rows["AnioAnteriorVentaNeta"].sum(),
        "PromHistoricoUnid": rows["PromHistoricoUnid"].sum(),
        "PromHistoricoVentaNeta": rows["PromHistoricoVentaNeta"].sum(),
        "HoyUnid": rows["HoyUnid"].sum(),
        "HoyVentaNeta": rows["HoyVentaNeta"].sum(),
    }
    total["VariacionUnidPct"] = (
        ((total["HoyUnid"] - total["AnioAnteriorUnid"]) / total["AnioAnteriorUnid"]) * 100
        if total["AnioAnteriorUnid"]
        else None
    )
    total["VariacionVentaPct"] = (
        ((total["HoyVentaNeta"] - total["AnioAnteriorVentaNeta"]) / total["AnioAnteriorVentaNeta"]) * 100
        if total["AnioAnteriorVentaNeta"]
        else None
    )
    total["VariacionPromUnidPct"] = (
        ((total["HoyUnid"] - total["PromHistoricoUnid"]) / total["PromHistoricoUnid"]) * 100
        if total["PromHistoricoUnid"]
        else None
    )
    total["VariacionPromVentaPct"] = (
        ((total["HoyVentaNeta"] - total["PromHistoricoVentaNeta"]) / total["PromHistoricoVentaNeta"]) * 100
        if total["PromHistoricoVentaNeta"]
        else None
    )
    return pd.concat([rows, pd.DataFrame([total])], ignore_index=True)


def _daily_row_html(row: pd.Series) -> str:
    row_class = "wally-total-row" if str(row["Dia"]) == "Total acumulado" else ""
    return (
        f'<tr class="{row_class}">'
        f'<td class="wally-hour">{escape(str(row["Dia"]))}</td>'
        f'<td>{_num(row["Historico2023Unid"])}</td><td>{_money(row["Historico2023VentaNeta"])}</td>'
        f'<td>{_num(row["Historico2024Unid"])}</td><td>{_money(row["Historico2024VentaNeta"])}</td>'
        f'<td>{_num(row["AnioAnteriorUnid"])}</td><td>{_money(row["AnioAnteriorVentaNeta"])}</td>'
        f'<td>{_num(row["PromHistoricoUnid"])}</td><td>{_money(row["PromHistoricoVentaNeta"])}</td>'
        f'<td>{_num(row["HoyUnid"])}</td><td>{_money(row["HoyVentaNeta"])}</td>'
        f'<td>{_format_pct(row["VariacionUnidPct"])}</td><td>{_format_pct(row["VariacionVentaPct"])}</td>'
        f'<td>{_format_pct(row["VariacionPromUnidPct"])}</td><td>{_format_pct(row["VariacionPromVentaPct"])}</td>'
        "</tr>"
    )


def _branch_range_total(rows: pd.DataFrame) -> pd.DataFrame:
    total = {
        "Ranking": "",
        "Sucursal": "Total",
        "Historico2023Unid": rows["Historico2023Unid"].sum(),
        "Historico2023VentaNeta": rows["Historico2023VentaNeta"].sum(),
        "Historico2024Unid": rows["Historico2024Unid"].sum(),
        "Historico2024VentaNeta": rows["Historico2024VentaNeta"].sum(),
        "AnioAnteriorUnid": rows["AnioAnteriorUnid"].sum(),
        "AnioAnteriorVentaNeta": rows["AnioAnteriorVentaNeta"].sum(),
        "HoyUnid": rows["HoyUnid"].sum(),
        "HoyVentaNeta": rows["HoyVentaNeta"].sum(),
    }
    total["VariacionUnidPct"] = (
        ((total["HoyUnid"] - total["AnioAnteriorUnid"]) / total["AnioAnteriorUnid"]) * 100
        if total["AnioAnteriorUnid"]
        else None
    )
    total["VariacionVentaPct"] = (
        ((total["HoyVentaNeta"] - total["AnioAnteriorVentaNeta"]) / total["AnioAnteriorVentaNeta"]) * 100
        if total["AnioAnteriorVentaNeta"]
        else None
    )
    return pd.concat([rows, pd.DataFrame([total])], ignore_index=True)


def _branch_range_row_html(row: pd.Series) -> str:
    row_class = "wally-total-row" if str(row["Sucursal"]).strip().lower() == "total" else ""
    return (
        f'<tr class="{row_class}">'
        f'<td class="wally-rank">{escape(str(row["Ranking"]))}</td>'
        f'<td class="wally-branch">{escape(str(row["Sucursal"]))}</td>'
        f'<td>{_num(row["Historico2023Unid"])}</td><td>{_money(row["Historico2023VentaNeta"])}</td>'
        f'<td>{_num(row["Historico2024Unid"])}</td><td>{_money(row["Historico2024VentaNeta"])}</td>'
        f'<td>{_num(row["AnioAnteriorUnid"])}</td><td>{_money(row["AnioAnteriorVentaNeta"])}</td>'
        f'<td>{_num(row["HoyUnid"])}</td><td>{_money(row["HoyVentaNeta"])}</td>'
        f'<td>{_format_pct(row["VariacionUnidPct"])}</td><td>{_format_pct(row["VariacionVentaPct"])}</td>'
        "</tr>"
    )


def render_branch_range_comparison_table(df: pd.DataFrame, years: dict[str, int]) -> None:
    if df.empty:
        st.info("No hay datos por sucursal para el rango consultado.")
        return

    rows = _branch_range_total(df.copy())
    body_html = "".join(_branch_range_row_html(row) for _, row in rows.iterrows())
    html = (
        "<style>"
        ".wally-range-table-wrap{width:max-content;max-width:100%;overflow-x:auto;border:1px solid #d8dee8;border-radius:8px;background:#fff;box-shadow:0 2px 10px rgba(15,23,42,.045);margin-bottom:12px}"
        "table.wally-range-table{width:auto;min-width:0;border-collapse:separate;border-spacing:0;font-size:.74rem;color:#0f172a;table-layout:auto}"
        ".wally-range-table th,.wally-range-table td{padding:6px 8px;border-right:1px solid #e2e8f0;border-bottom:1px solid #e2e8f0;white-space:nowrap;line-height:1.15}"
        ".wally-range-table thead tr:first-child th{background:#0f1f33;color:#fff;text-align:center;font-weight:800;letter-spacing:0}"
        ".wally-range-table thead tr:nth-child(2) th{color:#334155;text-align:center;font-weight:760}"
        ".wally-range-table .head-hist{background:#edf2f7!important;color:#0f172a!important}"
        ".wally-range-table .head-prev{background:#dbeafe!important;color:#1e3a8a!important}"
        ".wally-range-table .head-today{background:#dcfce7!important;color:#14532d!important}"
        ".wally-range-table .head-var{background:#f8fafc!important;color:#0f172a!important}"
        ".wally-range-table td{text-align:right;background:#fff}"
        ".wally-range-table .wally-rank{min-width:48px;text-align:center;color:#334155;background:#f8fafc;position:sticky;left:0;z-index:1}"
        ".wally-range-table .wally-branch{min-width:130px;text-align:left;font-weight:720;color:#334155;background:#fff;position:sticky;left:50px;z-index:1}"
        ".wally-range-table .wally-total-row td{background:#fff7ed;color:#7c2d12;font-weight:850}"
        ".wally-range-table th:not(:first-child),.wally-range-table td:not(:first-child){min-width:68px;max-width:104px}"
        ".wally-var-pos{color:#047857;font-weight:850}.wally-var-neg{color:#dc2626;font-weight:850}.wally-var-neu{color:#64748b;font-weight:850}.wally-var-na{color:#94a3b8;font-weight:850}"
        "</style>"
        '<div class="wally-range-table-wrap"><table class="wally-range-table"><thead>'
        "<tr>"
        '<th rowspan="2">Ranking</th>'
        '<th rowspan="2">Sucursal</th>'
        f'<th class="head-hist" colspan="2">{years["hist_1"]}</th>'
        f'<th class="head-hist" colspan="2">{years["hist_2"]}</th>'
        f'<th class="head-prev" colspan="2">{years["previous"]}</th>'
        f'<th class="head-today" colspan="2">Hoy {years["current"]}</th>'
        f'<th class="head-var" colspan="2">Variaci&oacute;n vs {years["previous"]}</th>'
        "</tr>"
        "<tr><th>Unid</th><th>Venta Neta</th><th>Unid</th><th>Venta Neta</th><th>Unid</th><th>Venta Neta</th><th>Unid</th><th>Venta Neta</th><th>Unid %</th><th>Venta %</th></tr>"
        f"</thead><tbody>{body_html}</tbody></table></div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def _shipment_row_html(row: pd.Series) -> str:
    row_class = "wally-total-row" if str(row["Embarque"]).strip().lower() == "total" else ""
    return (
        f'<tr class="{row_class}">'
        f'<td class="wally-shipment">{escape(str(row["Embarque"]))}</td>'
        f'<td class="wally-date">{escape(str(row["Fecha Entrada Dia 1"]))}</td>'
        f'<td>{_num(row["TVida"])}</td>'
        f'<td>{_num(row["Entrada"])}</td>'
        f'<td>{_num(row["Existencia Fisica"])}</td>'
        f'<td>{_num(row["Unidades Facturadas"])}</td>'
        f'<td>{_format_pct(row["%Rotacion"])}</td>'
        "</tr>"
    )


def _append_shipment_total(rows: pd.DataFrame) -> pd.DataFrame:
    total = {
        "Embarque": "Total",
        "Fecha Entrada Dia 1": "",
        "TVida": "",
        "Entrada": rows["Entrada"].sum(),
        "Existencia Fisica": rows["Existencia Fisica"].sum(),
        "Unidades Facturadas": rows["Unidades Facturadas"].sum(),
    }
    total["%Rotacion"] = (
        (total["Unidades Facturadas"] / total["Entrada"]) * 100
        if total["Entrada"]
        else None
    )
    return pd.concat([rows, pd.DataFrame([total])], ignore_index=True)


def render_shipment_summary_table(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No hay datos de embarques para mostrar.")
        return

    rows = _append_shipment_total(df.copy())
    body_html = "".join(_shipment_row_html(row) for _, row in rows.iterrows())
    html = (
        "<style>"
        ".wally-shipment-table-wrap{width:max-content;max-width:100%;overflow-x:auto;border:1px solid #d8dee8;border-radius:8px;background:#fff;box-shadow:0 2px 10px rgba(15,23,42,.045);margin-bottom:12px}"
        "table.wally-shipment-table{width:auto;min-width:0;border-collapse:separate;border-spacing:0;font-size:.76rem;color:#0f172a;table-layout:auto}"
        ".wally-shipment-table th,.wally-shipment-table td{padding:7px 9px;border-right:1px solid #e2e8f0;border-bottom:1px solid #e2e8f0;white-space:nowrap;line-height:1.15}"
        ".wally-shipment-table thead tr:first-child th{background:#0f1f33;color:#fff;text-align:center;font-weight:800;letter-spacing:0}"
        ".wally-shipment-table thead tr:nth-child(2) th{background:#f8fafc;color:#334155;text-align:center;font-weight:760}"
        ".wally-shipment-table .head-stock{background:#dcfce7!important;color:#14532d!important}"
        ".wally-shipment-table .head-sales{background:#dbeafe!important;color:#1e3a8a!important}"
        ".wally-shipment-table .head-rotation{background:#fef3c7!important;color:#92400e!important}"
        ".wally-shipment-table td{text-align:right;background:#fff}"
        ".wally-shipment-table .wally-shipment{min-width:78px;text-align:left;font-weight:800;color:#334155;background:#f8fafc;position:sticky;left:0;z-index:1}"
        ".wally-shipment-table .wally-date{text-align:center;color:#334155}"
        ".wally-shipment-table .wally-total-row td{background:#fff7ed;color:#7c2d12;font-weight:850}"
        ".wally-var-pos{color:#047857;font-weight:850}.wally-var-neg{color:#dc2626;font-weight:850}.wally-var-neu{color:#64748b;font-weight:850}.wally-var-na{color:#94a3b8;font-weight:850}"
        "</style>"
        '<div class="wally-shipment-table-wrap"><table class="wally-shipment-table"><thead>'
        "<tr>"
        '<th rowspan="2">Embarque</th>'
        '<th rowspan="2">Fecha entrada dia 1</th>'
        '<th rowspan="2">TVida</th>'
        '<th class="head-stock" colspan="2">Inventario</th>'
        '<th class="head-sales" colspan="1">Facturacion desde dia 1</th>'
        '<th class="head-rotation" colspan="1">Rotacion</th>'
        "</tr>"
        "<tr><th>Entrada</th><th>Existencia Fisica</th><th>Unidades Facturadas</th><th>%Rotacion</th></tr>"
        f"</thead><tbody>{body_html}</tbody></table></div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def _performance_pct(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{float(value):,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def _budget_performance_pct(value: float | int | None) -> str:
    text = _performance_pct(value)
    if not text:
        return ""
    try:
        pct = float(value)
    except Exception:
        return text
    if pct >= 100:
        return f'<span class="wally-budget-ok">{escape(text)}</span>'
    return text


def _line_performance_total(rows: pd.DataFrame) -> pd.DataFrame:
    total = {
        "Linea": "TOTAL",
        "StockUnidades": rows["StockUnidades"].sum(),
        "VentasUnidades": rows["VentasUnidades"].sum(),
        "VentaQ": rows["VentaQ"].sum(),
        "VentaDolar": rows["VentaDolar"].sum(),
        "PresupuestoUnidades": rows["PresupuestoUnidades"].sum(),
        "PresupuestoVenta": rows["PresupuestoVenta"].sum(),
    }
    total["PorcVenta"] = 100 if total["VentaQ"] else 0
    total["CumplUnidades"] = (
        (total["VentasUnidades"] / total["PresupuestoUnidades"]) * 100
        if total["PresupuestoUnidades"]
        else None
    )
    total["CumplVenta"] = (
        (total["VentaQ"] / total["PresupuestoVenta"]) * 100
        if total["PresupuestoVenta"]
        else None
    )
    return pd.concat([rows, pd.DataFrame([total])], ignore_index=True)


def _line_performance_row_html(row: pd.Series) -> str:
    row_class = "wally-total-row" if str(row["Linea"]).strip().upper() == "TOTAL" else ""
    return (
        f'<tr class="{row_class}">'
        f'<td class="wally-line">{escape(str(row["Linea"]))}</td>'
        f'<td>{_num(row["StockUnidades"])}</td>'
        f'<td>{_num(row["VentasUnidades"])}</td>'
        f'<td>{_money(row["VentaQ"])}</td>'
        f'<td>{_usd(row["VentaDolar"])}</td>'
        f'<td>{_performance_pct(row["PorcVenta"])}</td>'
        f'<td>{_num(row["PresupuestoUnidades"])}</td>'
        f'<td>{_money(row["PresupuestoVenta"])}</td>'
        f'<td>{_budget_performance_pct(row["CumplUnidades"])}</td>'
        f'<td>{_budget_performance_pct(row["CumplVenta"])}</td>'
        "</tr>"
    )


def render_line_performance_table(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No hay datos de presupuesto por linea para el rango seleccionado.")
        return

    rows = _line_performance_total(df.copy())
    body_html = "".join(_line_performance_row_html(row) for _, row in rows.iterrows())
    html = (
        "<style>"
        ".wally-line-performance-wrap{width:max-content;max-width:100%;overflow-x:auto;border:1px solid #d8dee8;border-radius:8px;background:#fff;box-shadow:0 2px 10px rgba(15,23,42,.045);margin-bottom:18px}"
        "table.wally-line-performance{width:auto;min-width:0;border-collapse:separate;border-spacing:0;font-size:.74rem;color:#0f172a;table-layout:auto}"
        ".wally-line-performance th,.wally-line-performance td{padding:6px 7px;border-right:1px solid #d8dee8;border-bottom:1px solid #d8dee8;white-space:nowrap;line-height:1.15}"
        ".wally-line-performance thead tr:first-child th{background:#0f1f33;color:#fff;text-align:center;font-weight:850}"
        ".wally-line-performance thead tr:nth-child(2) th{background:#dff3fb;color:#0f172a;text-align:center;font-weight:800}"
        ".wally-line-performance .head-stock{background:#edf2f7!important;color:#0f172a!important}"
        ".wally-line-performance .head-sales{background:#dbeafe!important;color:#1e3a8a!important}"
        ".wally-line-performance .head-budget{background:#fef3c7!important;color:#92400e!important}"
        ".wally-line-performance .head-compliance{background:#dcfce7!important;color:#14532d!important}"
        ".wally-line-performance td{text-align:right;background:#fff}"
        ".wally-line-performance .wally-line{min-width:92px;text-align:left;font-weight:800;color:#334155;background:#f8fafc;position:sticky;left:0;z-index:1}"
        ".wally-line-performance th:not(:first-child),.wally-line-performance td:not(:first-child){min-width:58px;max-width:98px}"
        ".wally-line-performance .wally-total-row td{background:#fff7ed;color:#7c2d12;font-weight:900}"
        ".wally-line-performance .wally-budget-ok{color:#047857;font-weight:900}"
        "</style>"
        '<div class="wally-line-performance-wrap"><table class="wally-line-performance"><thead>'
        "<tr>"
        '<th rowspan="2">LINEA</th>'
        '<th class="head-stock" colspan="1">Stock</th>'
        '<th class="head-sales" colspan="4">VENTAS</th>'
        '<th class="head-budget" colspan="2">Presupuesto</th>'
        '<th class="head-compliance" colspan="2">Cumplimiento</th>'
        "</tr>"
        "<tr><th>Unidades</th><th>Unidades</th><th>VentaQ</th><th>VentaDolar</th><th>%Venta</th><th>Unidades</th><th>Venta</th><th>Unidades</th><th>Venta</th></tr>"
        f"</thead><tbody>{body_html}</tbody></table></div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_daily_comparison_table(df: pd.DataFrame, years: dict[str, int]) -> None:
    if df.empty:
        st.info("No hay datos diarios para el rango consultado.")
        return

    rows = _append_daily_total(df.copy())
    body_html = "".join(_daily_row_html(row) for _, row in rows.iterrows())
    html = (
        "<style>"
        ".wally-hour-table-wrap{width:max-content;max-width:100%;overflow-x:auto;border:1px solid #d8dee8;border-radius:8px;background:#fff;box-shadow:0 2px 10px rgba(15,23,42,.045);margin-bottom:12px}"
        "table.wally-hour-table{width:auto;min-width:0;border-collapse:separate;border-spacing:0;font-size:.74rem;color:#0f172a;table-layout:auto}"
        ".wally-hour-table th,.wally-hour-table td{padding:6px 7px;border-right:1px solid #e2e8f0;border-bottom:1px solid #e2e8f0;white-space:nowrap;line-height:1.15}"
        ".wally-hour-table thead tr:first-child th{background:#0f1f33;color:#fff;text-align:center;font-weight:800;letter-spacing:0}"
        ".wally-hour-table thead tr:nth-child(2) th{color:#334155;text-align:center;font-weight:760}"
        ".wally-hour-table .head-hist{background:#edf2f7!important;color:#0f172a!important}"
        ".wally-hour-table .head-prev{background:#dbeafe!important;color:#1e3a8a!important}"
        ".wally-hour-table .head-prom{background:#fef3c7!important;color:#92400e!important}"
        ".wally-hour-table .head-today{background:#dcfce7!important;color:#14532d!important}"
        ".wally-hour-table .head-var{background:#f8fafc!important;color:#0f172a!important}"
        ".wally-hour-table td{text-align:right;background:#fff}"
        ".wally-hour-table th:not(:first-child),.wally-hour-table td:not(:first-child){min-width:64px;max-width:92px}"
        ".wally-hour-table td:nth-child(3),.wally-hour-table td:nth-child(5),.wally-hour-table td:nth-child(7),.wally-hour-table td:nth-child(9){min-width:78px;max-width:98px}"
        ".wally-hour-table .wally-hour{min-width:52px;max-width:74px;text-align:center;font-weight:720;color:#334155;background:#f8fafc;position:sticky;left:0;z-index:1}"
        ".wally-hour-table .wally-total-row td{background:#fff7ed;color:#7c2d12;font-weight:850}"
        ".wally-var-pos{color:#047857;font-weight:850}.wally-var-neg{color:#dc2626;font-weight:850}.wally-var-neu{color:#64748b;font-weight:850}.wally-var-na{color:#94a3b8;font-weight:850}"
        "</style>"
        '<div class="wally-hour-table-wrap"><table class="wally-hour-table"><thead>'
        "<tr>"
        '<th rowspan="2">Dia</th>'
        f'<th class="head-hist" colspan="2">{years["hist_1"]}</th>'
        f'<th class="head-hist" colspan="2">{years["hist_2"]}</th>'
        f'<th class="head-prev" colspan="2">{years["previous"]}</th>'
        '<th class="head-prom" colspan="2">PromHistorico</th>'
        f'<th class="head-today" colspan="2">Hoy {years["current"]}</th>'
        f'<th class="head-var" colspan="2">Variaci&oacute;n vs {years["previous"]}</th>'
        '<th class="head-var" colspan="2">Variaci&oacute;n vs PromHistorico</th>'
        "</tr>"
        "<tr><th>Unid</th><th>Venta Neta</th><th>Unid</th><th>Venta Neta</th><th>Unid</th><th>Venta Neta</th><th>Unid</th><th>Venta Neta</th><th>Unid</th><th>Venta Neta</th><th>Unid %</th><th>Venta %</th><th>Unid %</th><th>Venta %</th></tr>"
        f"</thead><tbody>{body_html}</tbody></table></div>"
    )
    st.markdown(html, unsafe_allow_html=True)
