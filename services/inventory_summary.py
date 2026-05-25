from __future__ import annotations

import pandas as pd


def resumen_embarque(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame(
            columns=["Embarque", "TVida", "Entrada", "Existencia Fisica", "Unidades Facturadas", "%Rotacion"]
        )
    shipment_table = (
        data.groupby("Embarque", dropna=False, as_index=False)
        .agg(
            TVida=("TVida", "min"),
            ExistFisica=("ExistFisica", "sum"),
            UnidFact=("UnidFact", "sum"),
            Entradas=("Entradas", "sum"),
        )
        .sort_values(["TVida", "Embarque"], ascending=[True, True])
    )
    shipment_table["%Rotacion"] = shipment_table["UnidFact"] / shipment_table["Entradas"].replace({0: pd.NA})
    shipment_table["%Rotacion"] = shipment_table["%Rotacion"].fillna(0)
    return shipment_table.rename(
        columns={
            "Entradas": "Entrada",
            "ExistFisica": "Existencia Fisica",
            "UnidFact": "Unidades Facturadas",
        }
    )[["Embarque", "TVida", "Entrada", "Existencia Fisica", "Unidades Facturadas", "%Rotacion"]]
