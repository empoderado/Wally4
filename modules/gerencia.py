from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from services import db
from services.branches import filter_frame
from services.catalog import get_code
from services.charts import WALLY_COLORS, apply_chart_theme
from services.exports import dataframe_to_excel_bytes, export_filename
from services.executive_tables import (
    render_branch_range_comparison_table,
    render_daily_comparison_table,
    render_hourly_comparison_table,
    render_line_performance_table,
    render_shipment_summary_table,
    render_branch_today_comparison_table,
    render_shipment_summary_table_style_daily,
    render_subline_performance_table,
)
from services.formatting import money, number, percent
from services.local_store import connect, get_param
from services.ui import code_footer, display_compact_table, metric_card, section_title, warning_box


def _default_business_date() -> date:
    return date.today()


def _comparison_dates(selected_date: date) -> list[date]:
    dates = []
    for offset in range(4):
        target_year = selected_date.year - offset
        try:
            dates.append(selected_date.replace(year=target_year))
        except ValueError:
            dates.append(selected_date.replace(year=target_year, day=28))
    return dates


def _elapsed_hours(selected_date: date) -> list[int]:
    today = date.today()
    if selected_date < today:
        return list(range(8, 24))
    current_hour = datetime.now().hour
    last_hour = max(8, min(23, current_hour))
    return list(range(8, last_hour + 1))


def _load_hourly_comparison(selected_date: date) -> tuple[pd.DataFrame, dict[str, int]]:
    target_dates = _comparison_dates(selected_date)
    year_map = {
        "current": target_dates[0].year,
        "previous": target_dates[1].year,
        "hist_2": target_dates[2].year,
        "hist_1": target_dates[3].year,
    }
    hours = _elapsed_hours(selected_date)
    params = tuple(day.strftime("%Y-%m-%d") for day in target_dates)
    placeholders = ", ".join("?" for _ in target_dates)
    raw = db.read_sql(
        f"""
        SELECT
            YEAR(CAST(Fecha AS date)) AS Anio,
            DATEPART(hour, CAST(HoraDocumento AS time)) AS Hora,
            SUM(ISNULL(Unidades, 0)) AS Unidades,
            SUM(ISNULL(VentaNetaQ, 0)) AS VentaNetaQ
        FROM {db.VIEW_VENTAS}
        WHERE CAST(Fecha AS date) IN ({placeholders})
          AND DATEPART(hour, CAST(HoraDocumento AS time)) BETWEEN 8 AND ?
        GROUP BY
            YEAR(CAST(Fecha AS date)),
            DATEPART(hour, CAST(HoraDocumento AS time))
        """,
        params + (hours[-1],),
    )

    for column in ["Anio", "Hora", "Unidades", "VentaNetaQ"]:
        if column not in raw.columns:
            raw[column] = 0

    rows = []
    for hour in hours:
        row = {"RangoHora": f"{hour} - {hour + 1}"}
        values = {}
        for alias, year in year_map.items():
            found = raw[(raw["Anio"] == year) & (raw["Hora"] == hour)] if not raw.empty else pd.DataFrame()
            units = float(found["Unidades"].sum()) if not found.empty else 0
            sales = float(found["VentaNetaQ"].sum()) if not found.empty else 0
            values[alias] = {"unid": units, "venta": sales}

        row["Historico2023Unid"] = values["hist_1"]["unid"]
        row["Historico2023VentaNeta"] = values["hist_1"]["venta"]
        row["Historico2024Unid"] = values["hist_2"]["unid"]
        row["Historico2024VentaNeta"] = values["hist_2"]["venta"]
        row["AnioAnteriorUnid"] = values["previous"]["unid"]
        row["AnioAnteriorVentaNeta"] = values["previous"]["venta"]
        row["HoyUnid"] = values["current"]["unid"]
        row["HoyVentaNeta"] = values["current"]["venta"]
        row["PromHistoricoUnid"] = (
            values["hist_1"]["unid"] + values["hist_2"]["unid"] + values["previous"]["unid"]
        ) / 3
        row["PromHistoricoVentaNeta"] = (
            values["hist_1"]["venta"] + values["hist_2"]["venta"] + values["previous"]["venta"]
        ) / 3
        row["VariacionUnidPct"] = (
            ((row["HoyUnid"] - row["AnioAnteriorUnid"]) / row["AnioAnteriorUnid"]) * 100
            if row["AnioAnteriorUnid"]
            else 0
        )
        row["VariacionVentaPct"] = (
            ((row["HoyVentaNeta"] - row["AnioAnteriorVentaNeta"]) / row["AnioAnteriorVentaNeta"]) * 100
            if row["AnioAnteriorVentaNeta"]
            else 0
        )
        row["VariacionPromUnidPct"] = (
            ((row["HoyUnid"] - row["PromHistoricoUnid"]) / row["PromHistoricoUnid"]) * 100
            if row["PromHistoricoUnid"]
            else 0
        )
        row["VariacionPromVentaPct"] = (
            ((row["HoyVentaNeta"] - row["PromHistoricoVentaNeta"]) / row["PromHistoricoVentaNeta"]) * 100
            if row["PromHistoricoVentaNeta"]
            else 0
        )
        rows.append(row)
    return pd.DataFrame(rows), year_map


def _date_range(start_date: date, end_date: date) -> list[date]:
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    days = (end_date - start_date).days
    return [start_date + timedelta(days=offset) for offset in range(days + 1)]


def _same_month_day(source_date: date, target_year: int) -> date:
    try:
        return source_date.replace(year=target_year)
    except ValueError:
        return source_date.replace(year=target_year, day=28)


def _load_daily_comparison(start_date: date, end_date: date) -> tuple[pd.DataFrame, dict[str, int]]:
    current_year = date.today().year
    year_map = {
        "current": current_year,
        "previous": current_year - 1,
        "hist_2": current_year - 2,
        "hist_1": current_year - 3,
    }
    current_dates = _date_range(start_date, end_date)
    query_dates = []
    for current_day in current_dates:
        for year in year_map.values():
            query_dates.append(_same_month_day(current_day, year))
    unique_dates = sorted(set(query_dates))
    placeholders = ", ".join("?" for _ in unique_dates)
    raw = db.read_sql(
        f"""
        SELECT
            YEAR(CAST(Fecha AS date)) AS Anio,
            MONTH(CAST(Fecha AS date)) AS Mes,
            DAY(CAST(Fecha AS date)) AS Dia,
            SUM(ISNULL(Unidades, 0)) AS Unidades,
            SUM(ISNULL(VentaNetaQ, 0)) AS VentaNetaQ
        FROM {db.VIEW_VENTAS}
        WHERE CAST(Fecha AS date) IN ({placeholders})
        GROUP BY
            YEAR(CAST(Fecha AS date)),
            MONTH(CAST(Fecha AS date)),
            DAY(CAST(Fecha AS date))
        """,
        tuple(day.strftime("%Y-%m-%d") for day in unique_dates),
    )

    for column in ["Anio", "Mes", "Dia", "Unidades", "VentaNetaQ"]:
        if column not in raw.columns:
            raw[column] = 0

    rows = []
    for current_day in current_dates:
        row = {"Dia": current_day.day}
        values = {}
        for alias, year in year_map.items():
            target_day = _same_month_day(current_day, year)
            found = (
                raw[
                    (raw["Anio"] == target_day.year)
                    & (raw["Mes"] == target_day.month)
                    & (raw["Dia"] == target_day.day)
                ]
                if not raw.empty
                else pd.DataFrame()
            )
            units = float(found["Unidades"].sum()) if not found.empty else 0
            sales = float(found["VentaNetaQ"].sum()) if not found.empty else 0
            values[alias] = {"unid": units, "venta": sales}

        row["Historico2023Unid"] = values["hist_1"]["unid"]
        row["Historico2023VentaNeta"] = values["hist_1"]["venta"]
        row["Historico2024Unid"] = values["hist_2"]["unid"]
        row["Historico2024VentaNeta"] = values["hist_2"]["venta"]
        row["AnioAnteriorUnid"] = values["previous"]["unid"]
        row["AnioAnteriorVentaNeta"] = values["previous"]["venta"]
        row["PromHistoricoUnid"] = (
            values["hist_1"]["unid"] + values["hist_2"]["unid"] + values["previous"]["unid"]
        ) / 3
        row["PromHistoricoVentaNeta"] = (
            values["hist_1"]["venta"] + values["hist_2"]["venta"] + values["previous"]["venta"]
        ) / 3
        row["HoyUnid"] = values["current"]["unid"]
        row["HoyVentaNeta"] = values["current"]["venta"]
        row["VariacionUnidPct"] = (
            ((row["HoyUnid"] - row["AnioAnteriorUnid"]) / row["AnioAnteriorUnid"]) * 100
            if row["AnioAnteriorUnid"]
            else None
        )
        row["VariacionVentaPct"] = (
            ((row["HoyVentaNeta"] - row["AnioAnteriorVentaNeta"]) / row["AnioAnteriorVentaNeta"]) * 100
            if row["AnioAnteriorVentaNeta"]
            else None
        )
        row["VariacionPromUnidPct"] = (
            ((row["HoyUnid"] - row["PromHistoricoUnid"]) / row["PromHistoricoUnid"]) * 100
            if row["PromHistoricoUnid"]
            else None
        )
        row["VariacionPromVentaPct"] = (
            ((row["HoyVentaNeta"] - row["PromHistoricoVentaNeta"]) / row["PromHistoricoVentaNeta"]) * 100
            if row["PromHistoricoVentaNeta"]
            else None
        )
        rows.append(row)
    return pd.DataFrame(rows), year_map


def _load_range_year_comparison(start_date: date, end_date: date) -> pd.DataFrame:
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    current_year = date.today().year
    years = [current_year - 3, current_year - 2, current_year - 1, current_year]
    current_dates = _date_range(start_date, end_date)
    query_dates = []
    range_by_year = {}
    for year in years:
        mapped_dates = [_same_month_day(day, year) for day in current_dates]
        range_by_year[year] = (min(mapped_dates), max(mapped_dates))
        query_dates.extend(mapped_dates)

    unique_dates = sorted(set(query_dates))
    if not unique_dates:
        return pd.DataFrame(columns=["Anio", "RangoFecha", "VentaNetaQ", "Unidades"])

    placeholders = ", ".join("?" for _ in unique_dates)
    raw = db.read_sql(
        f"""
        SELECT
            YEAR(CAST(Fecha AS date)) AS Anio,
            SUM(ISNULL(VentaNetaQ, 0)) AS VentaNetaQ,
            SUM(ISNULL(Unidades, 0)) AS Unidades
        FROM {db.VIEW_VENTAS}
        WHERE CAST(Fecha AS date) IN ({placeholders})
        GROUP BY YEAR(CAST(Fecha AS date))
        """,
        tuple(day.strftime("%Y-%m-%d") for day in unique_dates),
    )

    for column in ["Anio", "VentaNetaQ", "Unidades"]:
        if column not in raw.columns:
            raw[column] = 0

    rows = []
    for year in years:
        found = raw[raw["Anio"] == year] if not raw.empty else pd.DataFrame()
        range_start, range_end = range_by_year[year]
        rows.append(
            {
                "Anio": year,
                "RangoFecha": f"{range_start:%Y-%m-%d} a {range_end:%Y-%m-%d}",
                "VentaNetaQ": float(found["VentaNetaQ"].sum()) if not found.empty else 0,
                "Unidades": float(found["Unidades"].sum()) if not found.empty else 0,
            }
        )
    return pd.DataFrame(rows)


def _load_branch_range_comparison(start_date: date, end_date: date) -> tuple[pd.DataFrame, dict[str, int], int]:
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    current_year = date.today().year
    year_map = {
        "current": current_year,
        "previous": current_year - 1,
        "hist_2": current_year - 2,
        "hist_1": current_year - 3,
    }
    years = [year_map["hist_1"], year_map["hist_2"], year_map["previous"], year_map["current"]]
    current_dates = _date_range(start_date, end_date)
    query_dates = []
    for year in years:
        query_dates.extend(_same_month_day(day, year) for day in current_dates)

    unique_dates = sorted(set(query_dates))
    if not unique_dates:
        return pd.DataFrame(), year_map, year_map["previous"]

    placeholders = ", ".join("?" for _ in unique_dates)
    raw = db.read_sql(
        f"""
        SELECT
            YEAR(CAST(Fecha AS date)) AS Anio,
            Sucursal,
            SUM(ISNULL(Unidades, 0)) AS Unidades,
            SUM(ISNULL(VentaNetaQ, 0)) AS VentaNetaQ
        FROM {db.VIEW_VENTAS}
        WHERE CAST(Fecha AS date) IN ({placeholders})
        GROUP BY
            YEAR(CAST(Fecha AS date)),
            Sucursal
        """,
        tuple(day.strftime("%Y-%m-%d") for day in unique_dates),
    )
    for column in ["Anio", "Sucursal", "Unidades", "VentaNetaQ"]:
        if column not in raw.columns:
            raw[column] = "" if column == "Sucursal" else 0

    branches = (
        raw["Sucursal"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().sort_values().unique().tolist()
        if not raw.empty
        else []
    )
    rows = []
    for branch in branches:
        row = {"Sucursal": branch}
        values = {}
        for alias, year in year_map.items():
            found = raw[(raw["Anio"] == year) & (raw["Sucursal"].astype(str).str.strip() == branch)] if not raw.empty else pd.DataFrame()
            units = float(found["Unidades"].sum()) if not found.empty else 0
            sales = float(found["VentaNetaQ"].sum()) if not found.empty else 0
            values[alias] = {"unid": units, "venta": sales}

        row["Historico2023Unid"] = values["hist_1"]["unid"]
        row["Historico2023VentaNeta"] = values["hist_1"]["venta"]
        row["Historico2024Unid"] = values["hist_2"]["unid"]
        row["Historico2024VentaNeta"] = values["hist_2"]["venta"]
        row["AnioAnteriorUnid"] = values["previous"]["unid"]
        row["AnioAnteriorVentaNeta"] = values["previous"]["venta"]
        row["HoyUnid"] = values["current"]["unid"]
        row["HoyVentaNeta"] = values["current"]["venta"]

        best_year = year_map["previous"]
        best_total_sales = -1
        for alias, year in [("hist_1", year_map["hist_1"]), ("hist_2", year_map["hist_2"]), ("previous", year_map["previous"])]:
            found_year = raw[raw["Anio"] == year] if not raw.empty else pd.DataFrame()
            total_sales = float(found_year["VentaNetaQ"].sum()) if not found_year.empty else 0.0
            if total_sales > best_total_sales:
                best_total_sales = total_sales
                best_year = year

        if best_year == year_map["hist_1"]:
            best_unid = row["Historico2023Unid"]
            best_venta = row["Historico2023VentaNeta"]
        elif best_year == year_map["hist_2"]:
            best_unid = row["Historico2024Unid"]
            best_venta = row["Historico2024VentaNeta"]
        else: # year_map["previous"]
            best_unid = row["AnioAnteriorUnid"]
            best_venta = row["AnioAnteriorVentaNeta"]

        row["VariacionUnidPct"] = (
            ((row["HoyUnid"] - best_unid) / best_unid) * 100
            if best_unid
            else None
        )
        row["VariacionVentaPct"] = (
            ((row["HoyVentaNeta"] - best_venta) / best_venta) * 100
            if best_venta
            else None
        )
        rows.append(row)

    result = pd.DataFrame(rows)
    
    best_year = year_map["previous"]
    best_total_sales = -1
    for alias, year in [("hist_1", year_map["hist_1"]), ("hist_2", year_map["hist_2"]), ("previous", year_map["previous"])]:
        found_year = raw[raw["Anio"] == year] if not raw.empty else pd.DataFrame()
        total_sales = float(found_year["VentaNetaQ"].sum()) if not found_year.empty else 0.0
        if total_sales > best_total_sales:
            best_total_sales = total_sales
            best_year = year

    if result.empty:
        return result, year_map, best_year
    result = result.sort_values(["HoyVentaNeta", "AnioAnteriorVentaNeta", "Sucursal"], ascending=[False, False, True]).reset_index(drop=True)
    result.insert(0, "Ranking", range(1, len(result) + 1))
    return result, year_map, best_year


def _load_branch_today_comparison() -> tuple[pd.DataFrame, dict[str, int], int]:
    today = date.today()
    current_year = today.year
    year_map = {
        "current": current_year,
        "previous": current_year - 1,
        "hist_2": current_year - 2,
        "hist_1": current_year - 3,
    }
    years = [year_map["hist_1"], year_map["hist_2"], year_map["previous"], year_map["current"]]
    
    query_dates = [_same_month_day(today, year) for year in years]
    unique_dates = sorted(set(query_dates))
    if not unique_dates:
        return pd.DataFrame(), year_map, year_map["previous"]

    placeholders = ", ".join("?" for _ in unique_dates)
    raw = db.read_sql(
        f"""
        SELECT
            YEAR(CAST(Fecha AS date)) AS Anio,
            Sucursal,
            SUM(ISNULL(Unidades, 0)) AS Unidades,
            SUM(ISNULL(VentaNetaQ, 0)) AS VentaNetaQ
        FROM {db.VIEW_VENTAS}
        WHERE CAST(Fecha AS date) IN ({placeholders})
        GROUP BY
            YEAR(CAST(Fecha AS date)),
            Sucursal
        """,
        tuple(day.strftime("%Y-%m-%d") for day in unique_dates),
    )
    for column in ["Anio", "Sucursal", "Unidades", "VentaNetaQ"]:
        if column not in raw.columns:
            raw[column] = "" if column == "Sucursal" else 0

    branches = (
        raw["Sucursal"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().sort_values().unique().tolist()
        if not raw.empty
        else []
    )
    
    best_year = year_map["previous"]
    best_total_sales = -1
    for alias, year in [("hist_1", year_map["hist_1"]), ("hist_2", year_map["hist_2"]), ("previous", year_map["previous"])]:
        found_year = raw[raw["Anio"] == year] if not raw.empty else pd.DataFrame()
        total_sales = float(found_year["VentaNetaQ"].sum()) if not found_year.empty else 0.0
        if total_sales > best_total_sales:
            best_total_sales = total_sales
            best_year = year

    rows = []
    for branch in branches:
        row = {"Sucursal": branch}
        values = {}
        for alias, year in year_map.items():
            found = raw[(raw["Anio"] == year) & (raw["Sucursal"].astype(str).str.strip() == branch)] if not raw.empty else pd.DataFrame()
            units = float(found["Unidades"].sum()) if not found.empty else 0
            sales = float(found["VentaNetaQ"].sum()) if not found.empty else 0
            values[alias] = {"unid": units, "venta": sales}

        row["Historico2023Unid"] = values["hist_1"]["unid"]
        row["Historico2023VentaNeta"] = values["hist_1"]["venta"]
        row["Historico2024Unid"] = values["hist_2"]["unid"]
        row["Historico2024VentaNeta"] = values["hist_2"]["venta"]
        row["AnioAnteriorUnid"] = values["previous"]["unid"]
        row["AnioAnteriorVentaNeta"] = values["previous"]["venta"]
        row["HoyUnid"] = values["current"]["unid"]
        row["HoyVentaNeta"] = values["current"]["venta"]
        
        if best_year == year_map["hist_1"]:
            best_unid = row["Historico2023Unid"]
            best_venta = row["Historico2023VentaNeta"]
        elif best_year == year_map["hist_2"]:
            best_unid = row["Historico2024Unid"]
            best_venta = row["Historico2024VentaNeta"]
        else: # year_map["previous"]
            best_unid = row["AnioAnteriorUnid"]
            best_venta = row["AnioAnteriorVentaNeta"]

        row["VariacionUnidPct"] = (
            ((row["HoyUnid"] - best_unid) / best_unid) * 100
            if best_unid
            else None
        )
        row["VariacionVentaPct"] = (
            ((row["HoyVentaNeta"] - best_venta) / best_venta) * 100
            if best_venta
            else None
        )
        rows.append(row)

    result = pd.DataFrame(rows)
    if result.empty:
        return result, year_map, best_year
    result = result.sort_values(["HoyVentaNeta", "AnioAnteriorVentaNeta", "Sucursal"], ascending=[False, False, True]).reset_index(drop=True)
    result.insert(0, "Ranking", range(1, len(result) + 1))
    return result, year_map, best_year


def _load_recent_shipment_summary() -> pd.DataFrame:
    data = db.read_sql(
        f"""
        WITH PrimerasEntradas AS
        (
            SELECT TOP 20
                CAST(CodEmbarqueAbreviado AS varchar(100)) COLLATE DATABASE_DEFAULT AS Embarque,
                MIN(CAST(FechaEntrada AS date)) AS FechaPrimeraEntrada,
                SUM(ISNULL(UnidadesEntrada, 0)) AS Entrada
            FROM {db.VIEW_ENTRADAS}
            WHERE CodEmbarqueAbreviado IS NOT NULL
              AND LTRIM(RTRIM(CAST(CodEmbarqueAbreviado AS varchar(100)))) <> ''
            GROUP BY CodEmbarqueAbreviado
            HAVING SUM(ISNULL(UnidadesEntrada, 0)) > 10
            ORDER BY MIN(CAST(FechaEntrada AS date)) DESC, CodEmbarqueAbreviado ASC
        ),
        Existencia AS
        (
            SELECT
                CAST(CodEmbarqueAbreviado AS varchar(100)) COLLATE DATABASE_DEFAULT AS Embarque,
                SUM(ISNULL(ExistenciaFisica, 0)) AS ExistenciaFisica
            FROM {db.VIEW_EXISTENCIA}
            WHERE CodEmbarqueAbreviado IS NOT NULL
            GROUP BY CodEmbarqueAbreviado
        ),
        Facturacion AS
        (
            SELECT
                p.Embarque,
                SUM(ISNULL(v.Unidades, 0)) AS UnidadesFacturadas
            FROM PrimerasEntradas p
            LEFT JOIN {db.VIEW_VENTAS} v
                ON CAST(v.CodEmbarqueAbreviado AS varchar(100)) COLLATE DATABASE_DEFAULT = p.Embarque
               AND v.Trn = 'FV'
               AND v.Fecha >= p.FechaPrimeraEntrada
               AND v.Fecha < DATEADD(day, 1, CAST(GETDATE() AS date))
            GROUP BY p.Embarque
        )
        SELECT
            p.Embarque,
            p.FechaPrimeraEntrada AS [Fecha Entrada Dia 1],
            CAST(DATEDIFF(DAY, p.FechaPrimeraEntrada, CAST(GETDATE() AS date)) AS int) AS TVida,
            ISNULL(p.Entrada, 0) AS Entrada,
            ISNULL(e.ExistenciaFisica, 0) AS [Existencia Fisica],
            ISNULL(f.UnidadesFacturadas, 0) AS [Unidades Facturadas],
            CASE
                WHEN ISNULL(p.Entrada, 0) = 0 THEN NULL
                ELSE CAST(ISNULL(f.UnidadesFacturadas, 0) AS decimal(18, 6)) / NULLIF(p.Entrada, 0) * 100
            END AS [%Rotacion]
        FROM PrimerasEntradas p
        LEFT JOIN Existencia e
            ON p.Embarque = e.Embarque
        LEFT JOIN Facturacion f
            ON p.Embarque = f.Embarque
        ORDER BY p.FechaPrimeraEntrada DESC, p.Embarque ASC
        """
    )
    expected = {
        "Embarque": "",
        "Fecha Entrada Dia 1": "",
        "TVida": 0,
        "Entrada": 0,
        "Existencia Fisica": 0,
        "Unidades Facturadas": 0,
        "%Rotacion": None,
    }
    for column, default in expected.items():
        if column not in data.columns:
            data[column] = default
    if not data.empty:
        data["Fecha Entrada Dia 1"] = pd.to_datetime(data["Fecha Entrada Dia 1"]).dt.date
    return data[list(expected.keys())]


def _view_columns(view_name: str) -> set[str]:
    try:
        sample = db.read_sql(f"SELECT TOP 0 * FROM {view_name}")
        return set(sample.columns)
    except Exception:
        return set()


def _line_column(view_name: str) -> str:
    columns = _view_columns(view_name)
    if "Descripcion3Tabla4" in columns:
        return "Descripcion3Tabla4"
    return "Linea"


def _line_group_expr(view_name: str) -> str:
    columns = _view_columns(view_name)
    if "Descripcion3Tabla4" in columns:
        return "UPPER(LTRIM(RTRIM(CAST(COALESCE(NULLIF(Descripcion3Tabla4, ''), Linea) AS varchar(250)))))"
    return "UPPER(LTRIM(RTRIM(CAST(Linea AS varchar(250)))))"


def _line_group_mapping(start_date: date, end_date: date) -> dict[str, str]:
    sales_expr = _line_group_expr(db.VIEW_VENTAS)
    frames = []
    try:
        range_mapping = db.read_sql(
            f"""
            SELECT DISTINCT
                UPPER(LTRIM(RTRIM(CAST(Linea AS varchar(250))))) AS LineaOriginal,
                {sales_expr} AS LineaAgrupada
            FROM {db.VIEW_VENTAS}
            WHERE Fecha >= ? AND Fecha < DATEADD(day, 1, ?)
              AND Linea IS NOT NULL
              AND LTRIM(RTRIM(CAST(Linea AS varchar(250)))) <> ''
            """,
            db.date_params(start_date, end_date),
        )
        if not range_mapping.empty:
            frames.append(range_mapping)
    except Exception:
        pass
    if not frames:
        try:
            frames.append(
                db.read_sql(
                    f"""
                    SELECT DISTINCT
                        UPPER(LTRIM(RTRIM(CAST(Linea AS varchar(250))))) AS LineaOriginal,
                        {sales_expr} AS LineaAgrupada
                    FROM {db.VIEW_VENTAS}
                    WHERE Linea IS NOT NULL
                      AND LTRIM(RTRIM(CAST(Linea AS varchar(250)))) <> ''
                    """
                )
            )
        except Exception:
            pass
    if not frames:
        return {}
    mapping = pd.concat(frames, ignore_index=True)
    if mapping.empty or "LineaOriginal" not in mapping.columns or "LineaAgrupada" not in mapping.columns:
        return {}
    mapping["LineaOriginal"] = mapping["LineaOriginal"].astype(str).str.strip().str.upper()
    mapping["LineaAgrupada"] = mapping["LineaAgrupada"].astype(str).str.strip().str.upper()
    mapping = mapping[(mapping["LineaOriginal"] != "") & (mapping["LineaAgrupada"] != "")]
    return dict(mapping.drop_duplicates("LineaOriginal")[["LineaOriginal", "LineaAgrupada"]].values)


def _normalize_budget_line(value: object, group_map: dict[str, str]) -> str:
    line = str(value or "").strip().upper()
    if not line:
        return ""
    if line in group_map:
        return group_map[line]

    coded_line = re.match(r"^[A-Z0-9]+\s+-\s+(.+)$", line)
    if coded_line:
        line = coded_line.group(1).strip()
    return group_map.get(line, line)


def _read_line_branch_budget(start_date: date, end_date: date) -> pd.DataFrame:
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    conn = connect()
    try:
        data = pd.read_sql_query(
            """
            SELECT
                UPPER(TRIM(linea)) AS Linea,
                sucursal AS Sucursal,
                SUM(unidades) AS PresupuestoUnidades,
                SUM(venta_q) AS PresupuestoVenta
            FROM pto_linea_sucursal
            WHERE fecha BETWEEN ? AND ?
            GROUP BY UPPER(TRIM(linea)), sucursal
            """,
            conn,
            params=(start_date.isoformat(), end_date.isoformat()),
        )
        data = filter_frame(data, ["Sucursal"])
        if data.empty:
            return pd.DataFrame(columns=["Linea", "PresupuestoUnidades", "PresupuestoVenta"])
        return data.groupby("Linea", as_index=False).agg(
            PresupuestoUnidades=("PresupuestoUnidades", "sum"),
            PresupuestoVenta=("PresupuestoVenta", "sum"),
        )
    finally:
        conn.close()


def _load_line_performance(start_date: date, end_date: date) -> pd.DataFrame:
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    sales_line_expr = _line_group_expr(db.VIEW_VENTAS)

    sales = db.read_sql(
        f"""
        SELECT
            {sales_line_expr} AS Linea,
            SUM(
                CASE
                    WHEN Trn = 'FV' THEN ISNULL(Unidades, 0)
                    WHEN Trn IN ('NC', 'NCC') THEN -ABS(ISNULL(Unidades, 0))
                    ELSE 0
                END
            ) AS VentasUnidades,
            SUM(
                CASE
                    WHEN Trn = 'FV' THEN ISNULL(VentaNetaQ, 0)
                    WHEN Trn IN ('NC', 'NCC') THEN -ABS(ISNULL(VentaNetaQ, 0))
                    ELSE 0
                END
            ) AS VentaQ
        FROM {db.VIEW_VENTAS}
        WHERE Fecha >= ? AND Fecha < DATEADD(day, 1, ?)
          AND Trn IN ('FV', 'NC', 'NCC')
          AND {sales_line_expr} <> ''
        GROUP BY {sales_line_expr}
        """,
        db.date_params(start_date, end_date),
    )
    stock = db.read_sql(
        f"""
        SELECT
            UPPER(LTRIM(RTRIM(CAST(Linea AS varchar(250))))) AS LineaOriginal,
            SUM(ISNULL(ExistenciaFisica, 0)) AS StockUnidades
        FROM {db.VIEW_EXISTENCIA}
        WHERE Linea IS NOT NULL
          AND LTRIM(RTRIM(CAST(Linea AS varchar(250)))) <> ''
        GROUP BY UPPER(LTRIM(RTRIM(CAST(Linea AS varchar(250)))))
        """
    )
    budget = _read_line_branch_budget(start_date, end_date)
    group_map = _line_group_mapping(start_date, end_date)
    if not stock.empty and "LineaOriginal" in stock.columns:
        stock["Linea"] = (
            stock["LineaOriginal"]
            .astype(str)
            .str.strip()
            .str.upper()
            .map(lambda value: group_map.get(value, value))
        )
        stock = stock.groupby("Linea", as_index=False).agg(StockUnidades=("StockUnidades", "sum"))
    if not budget.empty:
        budget["Linea"] = budget["Linea"].map(lambda value: _normalize_budget_line(value, group_map))

    for frame, defaults in [
        (sales, {"Linea": "", "VentasUnidades": 0, "VentaQ": 0}),
        (stock, {"Linea": "", "StockUnidades": 0}),
        (budget, {"Linea": "", "PresupuestoUnidades": 0, "PresupuestoVenta": 0}),
    ]:
        for column, default in defaults.items():
            if column not in frame.columns:
                frame[column] = default

    line_values = sorted(
        set(sales["Linea"].dropna().astype(str))
        | set(stock["Linea"].dropna().astype(str))
        | set(budget["Linea"].dropna().astype(str))
    )
    if not line_values:
        return pd.DataFrame()

    data = pd.DataFrame({"Linea": [line for line in line_values if line.strip()]})
    data = (
        data.merge(stock.groupby("Linea", as_index=False).agg(StockUnidades=("StockUnidades", "sum")), on="Linea", how="left")
        .merge(sales.groupby("Linea", as_index=False).agg(VentasUnidades=("VentasUnidades", "sum"), VentaQ=("VentaQ", "sum")), on="Linea", how="left")
        .merge(budget.groupby("Linea", as_index=False).agg(PresupuestoUnidades=("PresupuestoUnidades", "sum"), PresupuestoVenta=("PresupuestoVenta", "sum")), on="Linea", how="left")
        .fillna(0)
    )
    total_sale = float(data["VentaQ"].sum())
    exchange_rate = float(get_param("tipo_cambio_usd", "7.8") or 7.8)
    if exchange_rate <= 0:
        exchange_rate = 7.8
    data["VentaDolar"] = data["VentaQ"] / exchange_rate
    data["PorcVenta"] = data["VentaQ"].map(lambda value: (float(value) / total_sale * 100) if total_sale else 0)
    data["CumplUnidades"] = data.apply(
        lambda row: (float(row["VentasUnidades"]) / float(row["PresupuestoUnidades"]) * 100) if float(row["PresupuestoUnidades"] or 0) else None,
        axis=1,
    )
    data["CumplVenta"] = data.apply(
        lambda row: (float(row["VentaQ"]) / float(row["PresupuestoVenta"]) * 100) if float(row["PresupuestoVenta"] or 0) else None,
        axis=1,
    )
    return data.sort_values(["VentaQ", "VentasUnidades", "Linea"], ascending=[False, False, True]).reset_index(drop=True)


def _load_subline_performance(start_date: date, end_date: date) -> pd.DataFrame:
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    sales_line_expr = _line_group_expr(db.VIEW_VENTAS)

    sales = db.read_sql(
        f"""
        SELECT
            {sales_line_expr} AS Linea,
            UPPER(LTRIM(RTRIM(CAST(DescSubLinea AS varchar(250))))) AS Sublinea,
            SUM(
                CASE
                    WHEN Trn = 'FV' THEN ISNULL(Unidades, 0)
                    WHEN Trn IN ('NC', 'NCC') THEN -ABS(ISNULL(Unidades, 0))
                    ELSE 0
                END
            ) AS VentasUnidades,
            SUM(
                CASE
                    WHEN Trn = 'FV' THEN ISNULL(VentaNetaQ, 0)
                    WHEN Trn IN ('NC', 'NCC') THEN -ABS(ISNULL(VentaNetaQ, 0))
                    ELSE 0
                END
            ) AS VentaQ
        FROM {db.VIEW_VENTAS}
        WHERE Fecha >= ? AND Fecha < DATEADD(day, 1, ?)
          AND Trn IN ('FV', 'NC', 'NCC')
          AND {sales_line_expr} <> ''
          AND DescSubLinea IS NOT NULL AND LTRIM(RTRIM(CAST(DescSubLinea AS varchar(250)))) <> ''
        GROUP BY {sales_line_expr}, UPPER(LTRIM(RTRIM(CAST(DescSubLinea AS varchar(250)))))
        """,
        db.date_params(start_date, end_date),
    )
    stock = db.read_sql(
        f"""
        SELECT
            UPPER(LTRIM(RTRIM(CAST(Linea AS varchar(250))))) AS LineaOriginal,
            UPPER(LTRIM(RTRIM(CAST(DescSubLinea AS varchar(250))))) AS Sublinea,
            SUM(ISNULL(ExistenciaFisica, 0)) AS StockUnidades
        FROM {db.VIEW_EXISTENCIA}
        WHERE Linea IS NOT NULL AND LTRIM(RTRIM(CAST(Linea AS varchar(250)))) <> ''
          AND DescSubLinea IS NOT NULL AND LTRIM(RTRIM(CAST(DescSubLinea AS varchar(250)))) <> ''
        GROUP BY UPPER(LTRIM(RTRIM(CAST(Linea AS varchar(250))))), UPPER(LTRIM(RTRIM(CAST(DescSubLinea AS varchar(250)))))
        """
    )
    group_map = _line_group_mapping(start_date, end_date)
    if not stock.empty and "LineaOriginal" in stock.columns:
        stock["Linea"] = (
            stock["LineaOriginal"]
            .astype(str)
            .str.strip()
            .str.upper()
            .map(lambda value: group_map.get(value, value))
        )
        stock = stock.groupby(["Linea", "Sublinea"], as_index=False).agg(StockUnidades=("StockUnidades", "sum"))

    for frame, defaults in [
        (sales, {"Linea": "", "Sublinea": "", "VentasUnidades": 0, "VentaQ": 0}),
        (stock, {"Linea": "", "Sublinea": "", "StockUnidades": 0}),
    ]:
        for column, default in defaults.items():
            if column not in frame.columns:
                frame[column] = default

    keys_sales = sales[["Linea", "Sublinea"]].drop_duplicates()
    keys_stock = stock[["Linea", "Sublinea"]].drop_duplicates()
    combined_keys = pd.concat([keys_sales, keys_stock]).drop_duplicates().reset_index(drop=True)
    combined_keys = combined_keys[combined_keys["Linea"].str.strip() != ""]
    combined_keys = combined_keys[combined_keys["Sublinea"].str.strip() != ""]

    if combined_keys.empty:
        return pd.DataFrame()

    data = (
        combined_keys
        .merge(stock, on=["Linea", "Sublinea"], how="left")
        .merge(sales, on=["Linea", "Sublinea"], how="left")
        .fillna(0)
    )

    total_sale = float(data["VentaQ"].sum())
    exchange_rate = float(get_param("tipo_cambio_usd", "7.8") or 7.8)
    if exchange_rate <= 0:
        exchange_rate = 7.8
    data["VentaDolar"] = data["VentaQ"] / exchange_rate
    data["PorcVenta"] = data["VentaQ"].map(lambda value: (float(value) / total_sale * 100) if total_sale else 0)

    # Filter to exactly Blusas, Jeans, Faldas, Vestidos
    allowed_lines = {"BLUSAS", "JEANS", "FALDAS", "VESTIDOS"}
    data = data[data["Linea"].str.upper().isin(allowed_lines)].copy()

    # Sort lines by total stock descending, and sublines by stock units descending
    line_totals = data.groupby("Linea")["StockUnidades"].sum().reset_index()
    line_stock_map = dict(zip(line_totals["Linea"], line_totals["StockUnidades"]))
    data["LineaTotalStock"] = data["Linea"].map(line_stock_map)
    data = data.sort_values(
        by=["LineaTotalStock", "Linea", "StockUnidades", "Sublinea"],
        ascending=[False, True, False, True]
    ).drop(columns=["LineaTotalStock"]).reset_index(drop=True)

    # Load budget mapping by line for subtotals
    budget = _read_line_branch_budget(start_date, end_date)
    if not budget.empty:
        budget["Linea"] = budget["Linea"].map(lambda value: _normalize_budget_line(value, group_map))
        budget_grouped = budget.groupby("Linea", as_index=False).agg(
            PresupuestoUnidades=("PresupuestoUnidades", "sum"),
            PresupuestoVenta=("PresupuestoVenta", "sum")
        )
        line_budget_map = {row["Linea"]: (row["PresupuestoUnidades"], row["PresupuestoVenta"]) for _, row in budget_grouped.iterrows()}
    else:
        line_budget_map = {}

    # Insert subtotal rows by line
    final_rows = []
    for line in data["Linea"].unique():
        line_data = data[data["Linea"] == line]
        
        # Append subline rows
        for _, row in line_data.iterrows():
            row_dict = row.to_dict()
            row_dict["PresupuestoUnidades"] = 0
            row_dict["PresupuestoVenta"] = 0
            row_dict["CumplUnidades"] = None
            row_dict["CumplVenta"] = None
            final_rows.append(row_dict)
            
        # Calculate and append subtotal row
        sub_units_pres = 0
        sub_venta_pres = 0
        if line in line_budget_map:
            sub_units_pres, sub_venta_pres = line_budget_map[line]
            
        sub_ventas_unidades = line_data["VentasUnidades"].sum()
        sub_venta_q = line_data["VentaQ"].sum()
        
        sub_cumpl_unid = (sub_ventas_unidades / sub_units_pres * 100) if sub_units_pres else None
        sub_cumpl_venta = (sub_venta_q / sub_venta_pres * 100) if sub_venta_pres else None
        
        final_rows.append({
            "Linea": line,
            "Sublinea": "Subtotal",
            "StockUnidades": line_data["StockUnidades"].sum(),
            "VentasUnidades": sub_ventas_unidades,
            "VentaQ": sub_venta_q,
            "VentaDolar": line_data["VentaDolar"].sum(),
            "PorcVenta": line_data["PorcVenta"].sum(),
            "PresupuestoUnidades": sub_units_pres,
            "PresupuestoVenta": sub_venta_pres,
            "CumplUnidades": sub_cumpl_unid,
            "CumplVenta": sub_cumpl_venta
        })
        
    if final_rows:
        data = pd.DataFrame(final_rows)
    else:
        data = pd.DataFrame(columns=data.columns)

    return data


def _load_gerencia(selected_date: date, daily_start: date, daily_end: date) -> tuple:
    target_dates = _comparison_dates(selected_date)
    params = tuple(day.strftime("%Y-%m-%d") for day in target_dates)
    placeholders = ", ".join("?" for _ in target_dates)
    summary = db.read_sql(
        f"""
        SELECT
            SUM(ISNULL(VentaNetaQ, 0)) AS VentaNetaQ,
            SUM(ISNULL(Unidades, 0)) AS Unidades,
            COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END) AS Facturas,
            SUM(VentaBruta) AS VentaBruta,
            SUM(DescuentoValor) AS DescuentoQ,
            SUM(CostoTotal) AS CostoTotal,
            SUM(ISNULL(VentaNetaQ, 0)) / 1.12 - SUM(CostoTotal) AS MargenQ
        FROM {db.VIEW_VENTAS}
        WHERE Fecha >= ? AND Fecha < DATEADD(day, 1, ?)
        """,
        (target_dates[0], target_dates[0]),
    )
    comparison = db.read_sql(
        f"""
        SELECT
            YEAR(CAST(Fecha AS date)) AS Anio,
            CAST(Fecha AS date) AS Fecha,
            SUM(ISNULL(VentaNetaQ, 0)) AS VentaNetaQ,
            SUM(ISNULL(Unidades, 0)) AS Unidades
        FROM {db.VIEW_VENTAS}
        WHERE CAST(Fecha AS date) IN ({placeholders})
        GROUP BY YEAR(CAST(Fecha AS date)), CAST(Fecha AS date)
        ORDER BY Anio DESC
        """,
        params,
    )
    if "Fecha" not in comparison.columns:
        comparison = pd.DataFrame(columns=["Anio", "Fecha", "VentaNetaQ", "Unidades"])
    if not comparison.empty:
        comparison["Fecha"] = pd.to_datetime(comparison["Fecha"]).dt.date
    expected = pd.DataFrame(
        {
            "Anio": [day.year for day in target_dates],
            "Fecha": target_dates,
        }
    )
    comparison = expected.merge(comparison, on=["Anio", "Fecha"], how="left")
    comparison[["VentaNetaQ", "Unidades"]] = comparison[["VentaNetaQ", "Unidades"]].fillna(0)
    comparison = comparison.sort_values("Anio", ascending=True).reset_index(drop=True)
    hourly, years = _load_hourly_comparison(selected_date)
    daily, daily_years = _load_daily_comparison(daily_start, daily_end)
    range_comparison = _load_range_year_comparison(daily_start, daily_end)
    branch_range_comparison, branch_range_years, branch_range_best_year = _load_branch_range_comparison(daily_start, daily_end)
    line_performance = _load_line_performance(daily_start, daily_end)
    shipment_summary = _load_recent_shipment_summary()
    today_comparison, today_years, today_best_year = _load_branch_today_comparison()
    return (
        summary,
        comparison,
        range_comparison,
        branch_range_comparison,
        branch_range_years,
        branch_range_best_year,
        line_performance,
        shipment_summary,
        hourly,
        daily,
        years,
        daily_years,
        today_comparison,
        today_years,
        today_best_year,
    )


def render() -> None:
    today = date.today()
    filter_cols = st.columns([1, 1.35, 1, 1])
    with filter_cols[0]:
        selected_date = st.date_input(
            "Fecha analisis",
            value=_default_business_date(),
            key="gerencia_fecha_analisis",
        )
    with filter_cols[1]:
        daily_mode = st.radio(
            "Rango tabla diaria",
            ["Mes actual automatico", "Rango personalizado"],
            horizontal=True,
            key="gerencia_daily_mode",
        )
    if daily_mode == "Mes actual automatico":
        daily_start = today.replace(day=1)
        daily_end = today
        with filter_cols[2]:
            st.date_input("Fecha inicio", value=daily_start, key="gerencia_auto_daily_start", disabled=True)
        with filter_cols[3]:
            st.date_input("Fecha fin", value=daily_end, key="gerencia_auto_daily_end", disabled=True)
    else:
        with filter_cols[2]:
            daily_start = st.date_input("Fecha inicio", value=today.replace(day=1), key="gerencia_daily_start")



        with filter_cols[3]:
            daily_end = st.date_input("Fecha fin", value=today, key="gerencia_daily_end")

    try:
        (
            summary,
            comparison,
            range_comparison,
            branch_range_comparison,
            branch_range_years,
            branch_range_best_year,
            line_performance,
            shipment_summary,
            hourly,
            daily,
            years,
            daily_years,
            today_comparison,
            today_years,
            today_best_year,
        ) = _load_gerencia(selected_date, daily_start, daily_end)
    except Exception as exc:
        st.error("No se pudo cargar la pagina de gerencia.")
        st.exception(exc)
        return

    if summary.empty:
        warning_box("No hay datos para la fecha seleccionada.")
        return

    row = summary.iloc[0].fillna(0)
    venta = float(row["VentaNetaQ"] or 0)
    unidades = float(row["Unidades"] or 0)
    facturas = float(row["Facturas"] or 0)
    margen_sin_iva = float(row["MargenQ"] or 0)
    costo = float(row.get("CostoTotal", 0) or 0)
    margen_con_iva = venta - costo
    ticket = venta / facturas if facturas else 0
    upt = unidades / facturas if facturas else 0
    vr_unidad = venta / unidades if unidades else 0

    cols = st.columns(8)
    with cols[0]:
        metric_card("Venta Neta Q", money(venta))
    with cols[1]:
        metric_card("Unidades", number(unidades))
    with cols[2]:
        metric_card("Facturas", number(facturas))
    with cols[3]:
        metric_card("Ticket Promedio", money(ticket))
    with cols[4]:
        metric_card("UPT", number(upt, 2))
    with cols[5]:
        metric_card("Vr Unidad Prom.", money(vr_unidad))
    with cols[6]:
        metric_card("Marge Con IVA", money(margen_con_iva), percent(margen_con_iva / venta if venta else 0), positive=margen_con_iva >= 0)
    with cols[7]:
        metric_card("Margen sin IVA", money(margen_sin_iva), percent(margen_sin_iva / (venta / 1.12) if venta else 0), positive=margen_sin_iva >= 0)
    code_footer(*get_code("gerencia", "report"))

    top_tables = st.columns([1.2, 2.8], gap="medium")
    with top_tables[0]:
        section_title("Comparativo ultimos 4 anios")
        table = comparison.copy()
        table["Fecha"] = pd.to_datetime(table["Fecha"]).dt.date
        display_compact_table(table, show_total=False)
        code_footer(*get_code("gerencia", "year_table"))
    with top_tables[1]:
        st.markdown("&nbsp;", unsafe_allow_html=True)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    section_title("Comparativo dia actual vs anios anteriores")
    render_branch_today_comparison_table(today_comparison, today_years, today_best_year)
    code_footer(*get_code("gerencia", "today_comparison_table"))

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    section_title("Comparativo 4 anios rango fecha")
    render_branch_range_comparison_table(branch_range_comparison, branch_range_years, branch_range_best_year)
    code_footer(*get_code("gerencia", "range_year_table"))

    section_title("Tendencia de Facturacion por Hora")
    render_hourly_comparison_table(hourly, years)
    code_footer(*get_code("gerencia", "hour_table"))

    section_title("Tendencia de Facturacion por Dia")
    render_daily_comparison_table(daily, daily_years)
    code_footer(*get_code("gerencia", "day_table"))

    section_title("Rotacion por embarque")
    render_shipment_summary_table(shipment_summary)
    code_footer(*get_code("existencias", "shipment_table"))

    chart_years = comparison.copy()
    chart_years["Anio"] = chart_years["Anio"].astype(str)
    chart_cols = st.columns(2)
    with chart_cols[0]:
        section_title("Venta Neta por Ano")
        fig_sales = px.bar(
            chart_years,
            x="Anio",
            y="VentaNetaQ",
            color_discrete_sequence=[WALLY_COLORS[0]],
            text="VentaNetaQ",
        )
        fig_sales.update_traces(texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
        fig_sales.update_xaxes(title_text="Ano", type="category", categoryorder="array", categoryarray=chart_years["Anio"].tolist())
        fig_sales.update_yaxes(title_text="Venta Neta Q")
        fig_sales = apply_chart_theme(fig_sales, 260)
        st.plotly_chart(fig_sales, use_container_width=True)
    with chart_cols[1]:
        section_title("Unidades por Ano")
        fig_units = px.bar(
            chart_years,
            x="Anio",
            y="Unidades",
            color_discrete_sequence=[WALLY_COLORS[2]],
            text="Unidades",
        )
        fig_units.update_traces(texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
        fig_units.update_xaxes(title_text="Ano", type="category", categoryorder="array", categoryarray=chart_years["Anio"].tolist())
        fig_units.update_yaxes(title_text="Unidades")
        fig_units = apply_chart_theme(fig_units, 260)
        st.plotly_chart(fig_units, use_container_width=True)
    code_footer(*get_code("gerencia", "year_chart"))

    st.download_button(
        "Exportar gerencia a Excel",
        dataframe_to_excel_bytes(
            {
                "Resumen": summary,
                "Comparativo fecha": comparison,
                "Comparativo rango": range_comparison,
                "Comparativo rango sucursal": branch_range_comparison,
                "Desempeno por linea": line_performance,
                "Resumen embarques": shipment_summary,
                "Tendencia por hora": hourly,
                "Tendencia por dia": daily,
            }
        ),
        file_name=export_filename("wally_gerencia"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def render_producto() -> None:
    today = date.today()
    filter_cols = st.columns([1, 1.35, 1, 1])
    with filter_cols[0]:
        selected_date = st.date_input(
            "Fecha analisis",
            value=_default_business_date(),
            key="gerencia_prod_fecha_analisis",
        )
    with filter_cols[1]:
        daily_mode = st.radio(
            "Rango tabla diaria",
            ["Mes actual automatico", "Rango personalizado"],
            horizontal=True,
            key="gerencia_prod_daily_mode",
        )
    if daily_mode == "Mes actual automatico":
        daily_start = today.replace(day=1)
        daily_end = today
        with filter_cols[2]:
            st.date_input("Fecha inicio", value=daily_start, key="gerencia_prod_auto_daily_start", disabled=True)
        with filter_cols[3]:
            st.date_input("Fecha fin", value=daily_end, key="gerencia_prod_auto_daily_end", disabled=True)
    else:
        with filter_cols[2]:
            daily_start = st.date_input("Fecha inicio", value=today.replace(day=1), key="gerencia_prod_daily_start")
        with filter_cols[3]:
            daily_end = st.date_input("Fecha fin", value=today, key="gerencia_prod_daily_end")

    try:
        (
            summary,
            comparison,
            range_comparison,
            branch_range_comparison,
            branch_range_years,
            branch_range_best_year,
            line_performance,
            shipment_summary,
            hourly,
            daily,
            years,
            daily_years,
            today_comparison,
            today_years,
            today_best_year,
        ) = _load_gerencia(selected_date, daily_start, daily_end)
    except Exception as exc:
        st.error("No se pudo cargar la pagina de gerencia producto.")
        st.exception(exc)
        return

    if summary.empty:
        warning_box("No hay datos para la fecha seleccionada.")
        return

    row = summary.iloc[0].fillna(0)
    venta = float(row["VentaNetaQ"] or 0)
    unidades = float(row["Unidades"] or 0)
    facturas = float(row["Facturas"] or 0)
    margen_sin_iva = float(row["MargenQ"] or 0)
    costo = float(row.get("CostoTotal", 0) or 0)
    margen_con_iva = venta - costo
    ticket = venta / facturas if facturas else 0
    upt = unidades / facturas if facturas else 0
    vr_unidad = venta / unidades if unidades else 0

    cols = st.columns(8)
    with cols[0]:
        metric_card("Venta Neta Q", money(venta))
    with cols[1]:
        metric_card("Unidades", number(unidades))
    with cols[2]:
        metric_card("Facturas", number(facturas))
    with cols[3]:
        metric_card("Ticket Promedio", money(ticket))
    with cols[4]:
        metric_card("UPT", number(upt, 2))
    with cols[5]:
        metric_card("Vr Unidad Prom.", money(vr_unidad))
    with cols[6]:
        metric_card("Marge Con IVA", money(margen_con_iva), percent(margen_con_iva / venta if venta else 0), positive=margen_con_iva >= 0)
    with cols[7]:
        metric_card("Margen sin IVA", money(margen_sin_iva), percent(margen_sin_iva / (venta / 1.12) if venta else 0), positive=margen_sin_iva >= 0)
    code_footer(*get_code("gerencia", "report"))

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    section_title("Analisis de Desempeno Comercial por Linea")
    render_line_performance_table(line_performance)
    code_footer(*get_code("gerencia", "line_performance"))

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    section_title("Analisis de Desempeno Comercial por Linea y Sublinea")
    subline_performance = _load_subline_performance(daily_start, daily_end)
    render_subline_performance_table(subline_performance)
    code_footer(*get_code("gerencia", "subline_performance"))

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    section_title("Rotacion por embarque")
    render_shipment_summary_table_style_daily(shipment_summary)
    code_footer(*get_code("existencias", "shipment_table"))
