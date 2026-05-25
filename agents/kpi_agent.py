from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from services import db
from services.formatting import money, number, percent
from agents.sql_agent import QueryContext


@dataclass(frozen=True)
class KpiResult:
    dataframe: pd.DataFrame
    answer: str


def sales_summary(start_date, end_date, label: str) -> KpiResult:
    query = f"""
        SELECT
            SUM(ISNULL(VentaNetaQ, 0)) AS VentaNetaQ,
            SUM(ISNULL(Unidades, 0)) AS Unidades,
            COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END) AS Facturas,
            SUM(ISNULL(VentaBruta, 0)) AS VentaBruta,
            SUM(ISNULL(DescuentoValor, 0)) AS DescuentoQ,
            SUM(ISNULL(CostoTotal, 0)) AS CostoTotal,
            SUM(ISNULL(VentaNetaQ, 0)) - SUM(ISNULL(CostoTotal, 0)) AS MargenQ
        FROM {db.VIEW_VENTAS}
        WHERE CAST(Fecha AS date) BETWEEN ? AND ?
          AND Trn = 'FV'
    """
    df = db.read_sql(query, (start_date, end_date))
    row = _first_row(df)
    venta = _value(row, "VentaNetaQ")
    unidades = _value(row, "Unidades")
    facturas = _value(row, "Facturas")
    margen = _value(row, "MargenQ")
    ticket = venta / facturas if facturas else 0
    upt = unidades / facturas if facturas else 0
    vr_unidad = venta / unidades if unidades else 0
    margen_pct = margen / venta if venta else 0
    answer = (
        f"**Ventas {label} [{start_date}; {end_date}]**\n\n"
        f"1. **Venta Neta Q:** {money(venta)}\n\n"
        f"2. **Unidades:** {number(unidades)}\n\n"
        f"3. **Facturas:** {number(facturas)}\n\n"
        f"4. **Ticket Promedio:** {money(ticket)}\n\n"
        f"5. **UPT:** {number(upt, 2)}\n\n"
        f"6. **Vr Unid Prom:** {money(vr_unidad)}\n\n"
        f"7. **Margen:** {money(margen)} ({percent(margen_pct)})"
    )
    return KpiResult(df, answer)


def sales_by_branch(start_date, end_date, label: str, limit: int = 10) -> KpiResult:
    query = f"""
        SELECT
            Sucursal,
            SUM(ISNULL(VentaNetaQ, 0)) AS VentaNetaQ,
            SUM(ISNULL(Unidades, 0)) AS Unidades,
            COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END) AS Facturas,
            SUM(ISNULL(CostoTotal, 0)) AS CostoTotal,
            SUM(ISNULL(VentaNetaQ, 0)) - SUM(ISNULL(CostoTotal, 0)) AS MargenQ
        FROM {db.VIEW_VENTAS}
        WHERE CAST(Fecha AS date) BETWEEN ? AND ?
          AND Trn = 'FV'
        GROUP BY Sucursal
        ORDER BY VentaNetaQ DESC
    """
    df = db.read_sql(query, (start_date, end_date))
    if df.empty:
        return KpiResult(df, f"No encontre ventas por sucursal para {label} [{start_date}; {end_date}].")
    lines = [f"**Ventas por sucursal {label} [{start_date}; {end_date}]**"]
    total_venta = df["VentaNetaQ"].sum()
    total_unidades = df["Unidades"].sum()
    total_facturas = df["Facturas"].sum()
    total_margen = df["MargenQ"].sum()
    for idx, row in df.head(limit).iterrows():
        venta = _value(row, "VentaNetaQ")
        unidades = _value(row, "Unidades")
        facturas = _value(row, "Facturas")
        margen = _value(row, "MargenQ")
        ticket = venta / facturas if facturas else 0
        upt = unidades / facturas if facturas else 0
        vr_unidad = venta / unidades if unidades else 0
        lines.append(
            "\n"
            f"{idx + 1}. **{row['Sucursal']}**\n"
            f"   Venta: {money(venta)} | Unid: {number(unidades)} | Fact: {number(facturas)} | "
            f"Ticket: {money(ticket)} | UPT: {number(upt, 2)} | Vr Unid: {money(vr_unidad)} | "
            f"Margen: {money(margen)}"
        )
    lines.append(
        f"\n**Total:** Venta {money(total_venta)} | Unid {number(total_unidades)} | "
        f"Fact {number(total_facturas)} | Margen {money(total_margen)}"
    )
    return KpiResult(df, "\n".join(lines))


def inventory_by_branch(limit: int = 10) -> KpiResult:
    query = f"""
        SELECT
            Sucursal,
            SUM(ISNULL(ExistenciaFisica, 0)) AS Existencia
        FROM {db.VIEW_EXISTENCIA}
        GROUP BY Sucursal
        ORDER BY Existencia DESC
    """
    df = db.read_sql(query)
    if df.empty:
        return KpiResult(df, "No encontre datos de inventario en la vista autorizada.")
    lines = ["**Inventario por sucursal**"]
    total_existencia = df["Existencia"].sum()
    for idx, row in df.head(limit).iterrows():
        lines.append(f"\n{idx + 1}. **{row['Sucursal']}**: {number(row['Existencia'])} unidades fisicas")
    lines.append(f"\n**Total:** {number(total_existencia)} unidades fisicas")
    return KpiResult(df, "\n".join(lines))


def sales_by_seller(start_date, end_date, label: str, limit: int = 10) -> KpiResult:
    return _sales_grouped(
        start_date,
        end_date,
        label,
        dimension="Vendedor",
        title="Ventas por vendedor",
        limit=limit,
    )


def sales_by_shipment(start_date, end_date, label: str, limit: int = 10) -> KpiResult:
    return _sales_grouped(
        start_date,
        end_date,
        label,
        dimension="CodEmbarqueAbreviado",
        title="Ventas por embarque",
        limit=limit,
    )


def sales_by_line(start_date, end_date, label: str, limit: int = 10) -> KpiResult:
    return _sales_grouped(
        start_date,
        end_date,
        label,
        dimension="Linea",
        title="Ventas por linea",
        limit=limit,
    )


def best_customer(start_date, end_date, label: str, limit: int = 10, order_by: str = "venta") -> KpiResult:
    order_column = "Facturas" if order_by == "facturas" else "VentaNetaQ"
    title = "Clientes que mas veces compraron" if order_by == "facturas" else "Mejores clientes"
    query = f"""
        SELECT
            Cuenta,
            Cliente,
            SUM(ISNULL(VentaNetaQ, 0)) AS VentaNetaQ,
            SUM(ISNULL(Unidades, 0)) AS Unidades,
            COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END) AS Facturas,
            MAX(CAST(Fecha AS date)) AS UltimaCompra
        FROM {db.VIEW_VENTAS}
        WHERE CAST(Fecha AS date) BETWEEN ? AND ?
          AND Trn = 'FV'
          AND Cuenta IS NOT NULL
          AND Cliente IS NOT NULL
          AND UPPER(LTRIM(RTRIM(CAST(Cliente AS varchar(250))))) NOT IN
          (
              'CONSUMIDOR FINAL',
              'CLIENTE GENERAL',
              'SIN NOMBRE',
              'CF',
              'C/F'
          )
        GROUP BY Cuenta, Cliente
        ORDER BY {order_column} DESC, VentaNetaQ DESC
    """
    df = db.read_sql(query, (start_date, end_date))
    if df.empty:
        return KpiResult(df, f"No encontre clientes con compra para {label} [{start_date}; {end_date}].")
    lines = [f"**{title} {label} [{start_date}; {end_date}]**"]
    total_venta = df["VentaNetaQ"].sum()
    total_unidades = df["Unidades"].sum()
    total_facturas = df["Facturas"].sum()
    for idx, row in df.head(limit).iterrows():
        lines.append(
            f"\n{idx + 1}. **{row['Cliente']}** | Nit/DPI {row['Cuenta']}\n"
            f"   Venta {money(row['VentaNetaQ'])} | Unid {number(row['Unidades'])} | "
            f"Fact {number(row['Facturas'])} | Ultima compra {row['UltimaCompra']}"
        )
    lines.append(
        f"\n**Total:** Venta {money(total_venta)} | Unid {number(total_unidades)} | "
        f"Fact {number(total_facturas)}"
    )
    return KpiResult(df, "\n".join(lines))


def sales_year_comparison(limit_years: int = 4) -> KpiResult:
    query = f"""
        SELECT TOP ({limit_years})
            YEAR(CAST(Fecha AS date)) AS Anio,
            SUM(ISNULL(VentaNetaQ, 0)) AS VentaNetaQ,
            SUM(ISNULL(Unidades, 0)) AS Unidades,
            COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END) AS Facturas
        FROM {db.VIEW_VENTAS}
        WHERE Trn = 'FV'
        GROUP BY YEAR(CAST(Fecha AS date))
        ORDER BY Anio DESC
    """
    df = db.read_sql(query)
    if df.empty:
        return KpiResult(df, "No encontre datos para el comparativo anual.")
    df = df.sort_values("Anio")
    lines = ["**Comparativo anual de ventas**"]
    total_venta = df["VentaNetaQ"].sum()
    total_unidades = df["Unidades"].sum()
    total_facturas = df["Facturas"].sum()
    for _, row in df.iterrows():
        lines.append(
            f"\n**{int(row['Anio'])}:** Venta {money(row['VentaNetaQ'])} | "
            f"Unid {number(row['Unidades'])} | Fact {number(row['Facturas'])}"
        )
    lines.append(
        f"\n**Total:** Venta {money(total_venta)} | Unid {number(total_unidades)} | "
        f"Fact {number(total_facturas)}"
    )
    return KpiResult(df, "\n".join(lines))


def inventory_by_shipment(limit: int = 10) -> KpiResult:
    query = f"""
        SELECT
            CodEmbarqueAbreviado,
            MIN(ISNULL(TVida, 0)) AS TVida,
            SUM(ISNULL(ExistenciaFisica, 0)) AS Existencia
        FROM {db.VIEW_EXISTENCIA}
        GROUP BY CodEmbarqueAbreviado
        ORDER BY Existencia DESC
    """
    df = db.read_sql(query)
    if df.empty:
        return KpiResult(df, "No encontre inventario por embarque.")
    lines = ["**Inventario por embarque**"]
    total_existencia = df["Existencia"].sum()
    for idx, row in df.head(limit).iterrows():
        lines.append(
            f"\n{idx + 1}. **{row['CodEmbarqueAbreviado']}**: "
            f"{number(row['Existencia'])} unidades fisicas | TVida {number(row['TVida'])} dias"
        )
    lines.append(f"\n**Total:** {number(total_existencia)} unidades fisicas")
    return KpiResult(df, "\n".join(lines))


def inventory_reference(context: QueryContext) -> KpiResult:
    if not context.reference:
        return KpiResult(
            pd.DataFrame(),
            "Necesito que me indiques la referencia. Ejemplo: inventario de la referencia S506345 en Pradera.",
        )
    filters = ["Referencia = ?"]
    params: list[str] = [context.reference]
    if context.branch:
        filters.append("Sucursal = ?")
        params.append(context.branch)
    query = f"""
        SELECT
            Sucursal,
            Referencia,
            Talla,
            Color,
            CodEmbarqueAbreviado,
            SUM(ISNULL(ExistenciaFisica, 0)) AS ExistenciaFisica,
            SUM(ISNULL(ExistenciaDisponible, 0)) AS ExistenciaDisponible
        FROM {db.VIEW_EXISTENCIA}
        WHERE {" AND ".join(filters)}
        GROUP BY Sucursal, Referencia, Talla, Color, CodEmbarqueAbreviado
        ORDER BY Sucursal, Color, Talla
    """
    df = db.read_sql(query, params)
    if df.empty:
        target = f" en {context.branch}" if context.branch else ""
        return KpiResult(df, f"No encontre existencia para la referencia {context.reference}{target}.")
    branch_text = f" en {context.branch}" if context.branch else ""
    lines = [f"**Inventario referencia {context.reference}{branch_text}**"]
    total_fisica = df["ExistenciaFisica"].sum()
    total_disponible = df["ExistenciaDisponible"].sum()
    for _, row in df.head(context.limit).iterrows():
        lines.append(
            f"\n**{row['Sucursal']}** | Talla {row['Talla']} | Color {row['Color']} | "
            f"Emb {row['CodEmbarqueAbreviado']} | Fisica {number(row['ExistenciaFisica'])} | "
            f"Disponible {number(row['ExistenciaDisponible'])}"
        )
    lines.append(f"\n**Total:** Fisica {number(total_fisica)} | Disponible {number(total_disponible)}")
    return KpiResult(df, "\n".join(lines))


def _sales_grouped(start_date, end_date, label: str, dimension: str, title: str, limit: int) -> KpiResult:
    query = f"""
        SELECT
            {dimension},
            SUM(ISNULL(VentaNetaQ, 0)) AS VentaNetaQ,
            SUM(ISNULL(Unidades, 0)) AS Unidades,
            COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END) AS Facturas,
            SUM(ISNULL(VentaNetaQ, 0)) - SUM(ISNULL(CostoTotal, 0)) AS MargenQ
        FROM {db.VIEW_VENTAS}
        WHERE CAST(Fecha AS date) BETWEEN ? AND ?
          AND Trn = 'FV'
        GROUP BY {dimension}
        ORDER BY VentaNetaQ DESC
    """
    df = db.read_sql(query, (start_date, end_date))
    if df.empty:
        return KpiResult(df, f"No encontre datos para {title.lower()} {label} [{start_date}; {end_date}].")
    lines = [f"**{title} {label} [{start_date}; {end_date}]**"]
    total_venta = df["VentaNetaQ"].sum()
    total_unidades = df["Unidades"].sum()
    total_facturas = df["Facturas"].sum()
    total_margen = df["MargenQ"].sum() if "MargenQ" in df.columns else 0
    for idx, row in df.head(limit).iterrows():
        lines.append(
            f"\n{idx + 1}. **{row[dimension]}**: "
            f"Venta {money(row['VentaNetaQ'])} | Unid {number(row['Unidades'])} | "
            f"Fact {number(row['Facturas'])} | Margen {money(row.get('MargenQ', 0))}"
        )
    lines.append(
        f"\n**Total:** Venta {money(total_venta)} | Unid {number(total_unidades)} | "
        f"Fact {number(total_facturas)} | Margen {money(total_margen)}"
    )
    return KpiResult(df, "\n".join(lines))


def _first_row(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(dtype="object")
    return df.iloc[0]


def _value(row: pd.Series, key: str) -> float:
    if key not in row or pd.isna(row[key]):
        return 0.0
    return float(row[key])
