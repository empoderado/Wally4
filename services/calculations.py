from __future__ import annotations

import pandas as pd


def kpis_sucursal(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    data = df.copy()
    for column in ["Sucursal", "Unidades", "VentaNetaQ", "Facturas", "MargenQ", "DescuentoQ", "VentaBruta"]:
        if column not in data.columns:
            data[column] = "" if column == "Sucursal" else 0
    total_venta = float(data["VentaNetaQ"].sum()) if "VentaNetaQ" in data else 0
    data = data.sort_values("VentaNetaQ", ascending=False).reset_index(drop=True)
    data.insert(0, "Ranking", range(1, len(data) + 1))
    data["Upt"] = data["Unidades"] / data["Facturas"].replace({0: pd.NA})
    data["FactProm"] = data["VentaNetaQ"] / data["Facturas"].replace({0: pd.NA})
    data["VrPromedioUnidad"] = data["VentaNetaQ"] / data["Unidades"].replace({0: pd.NA})
    data["%Margen"] = data["MargenQ"] / data["VentaNetaQ"].replace({0: pd.NA})
    data["%Desc"] = data["DescuentoQ"] / data["VentaBruta"].replace({0: pd.NA})
    data["%VentaSuc"] = data["VentaNetaQ"] / total_venta if total_venta else 0
    data["Semáforo"] = data["%Margen"].map(_semaforo_margen)
    return data[
        [
            "Ranking",
            "Sucursal",
            "Unidades",
            "VentaNetaQ",
            "Facturas",
            "Upt",
            "FactProm",
            "VrPromedioUnidad",
            "MargenQ",
            "%Margen",
            "DescuentoQ",
            "%Desc",
            "%VentaSuc",
            "Semáforo",
        ]
    ]


def _semaforo_margen(value) -> str:
    try:
        margin = float(value)
    except Exception:
        return "Rojo"
    if margin >= 0.60:
        return "Verde"
    if margin >= 0.55:
        return "Amarillo"
    return "Rojo"
