from __future__ import annotations

import os
import sys
import sqlite3
import pandas as pd
from pathlib import Path

# Add project root to sys.path
APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from services import db
from services.local_store import connect as sqlite_connect
from services.exports import dataframe_to_excel_bytes

def get_local_assignments() -> pd.DataFrame:
    """Gets the latest assignment status and date from the SQLite database."""
    conn = sqlite_connect()
    try:
        query = """
            SELECT nit_dpi, estado, fecha_asignacion
            FROM crm_asignaciones
        """
        df = pd.read_sql(query, conn)
        if df.empty:
            return pd.DataFrame(columns=["nit_dpi", "estado_local", "fecha_asignacion_local"])
        
        # Clean nit_dpi
        df["nit_dpi"] = df["nit_dpi"].astype(str).str.strip()
        
        # Sort by fecha_asignacion descending, then drop duplicates to keep the latest one
        df = df.sort_values(by=["fecha_asignacion"], ascending=False)
        df = df.drop_duplicates(subset=["nit_dpi"], keep="first")
        
        # Rename columns to avoid confusion
        df = df.rename(columns={
            "estado": "estado_local",
            "fecha_asignacion": "fecha_asignacion_local"
        })
        return df
    except Exception as e:
        print(f"Error querying SQLite: {e}")
        return pd.DataFrame(columns=["nit_dpi", "estado_local", "fecha_asignacion_local"])
    finally:
        conn.close()

def get_majadas_crm_dataframe() -> pd.DataFrame:
    """Backward compatibility wrapper for Vía Majadas."""
    return get_branch_crm_dataframe("MAJADAS")

def get_branch_crm_dataframe(branch_name: str, segmentos: list[str] | None = None, sort_asc: bool = False) -> pd.DataFrame:
    """Queries SQL Server and SQLite to generate the complete CRM branch dataframe."""
    # 1. Query candidates from SQL Server
    where_clause = "AND DiasSinCompra >= 1"
    if segmentos:
        where_clause += f" AND SegmentoSinCompra IN ({db.sql_literal_list(segmentos)})"
        
    sort_order = "ASC" if sort_asc else "DESC"
    
    query_sql = f"""
        SELECT
            NitDpi,
            Cliente,
            Telefono,
            Celular,
            Email,
            FechaUltimaCompra,
            DiasSinCompra,
            SegmentoSinCompra,
            SucursalPreferida,
            VendedorUltimaFactura,
            FacturasTotales,
            UnidadesTotales,
            VentaNetaTotal,
            UnidadesFullPrecio,
            UnidadesPromocion,
            PorcentajeFullPrecio,
            PorcentajePromocion
        FROM {db.VIEW_CRM}
        WHERE NitDpi IN (
            SELECT DISTINCT Cuenta
            FROM {db.VIEW_VENTAS}
            WHERE Sucursal = ?
              AND Trn = 'FV'
              AND Cuenta IS NOT NULL
        )
          {where_clause}
        ORDER BY
            DiasSinCompra {sort_order},
            VentaNetaTotal DESC,
            FacturasTotales DESC,
            Cliente ASC
    """
    
    df_candidates = db.read_sql(query_sql, params=(branch_name,), apply_branch_filter=False)
    if df_candidates.empty:
        return pd.DataFrame()
        
    # 2. Get local assignments from SQLite to mark duplicates
    df_assignments = get_local_assignments()
    
    # 3. Merge dataframes to mark duplicate info / local management
    if not df_assignments.empty:
        # Clean merge keys
        df_candidates["NitDpi_Clean"] = df_candidates["NitDpi"].astype(str).str.strip()
        df_assignments["nit_dpi_Clean"] = df_assignments["nit_dpi"].astype(str).str.strip()
        
        df_merged = pd.merge(
            df_candidates,
            df_assignments,
            left_on="NitDpi_Clean",
            right_on="nit_dpi_Clean",
            how="left"
        )
        # Drop clean temporary columns
        df_merged = df_merged.drop(columns=["NitDpi_Clean", "nit_dpi_Clean", "nit_dpi"])
    else:
        df_merged = df_candidates.copy()
        df_merged["estado_local"] = None
        df_merged["fecha_asignacion_local"] = None

    # Replace None/NaN in local assignment status
    df_merged["estado_local"] = df_merged["estado_local"].fillna("Sin asignación local")
    df_merged["fecha_asignacion_local"] = df_merged.get("fecha_asignacion_local", pd.Series(dtype=object)).fillna("N/A")

    # 4. Add Consecutivo de fila
    df_merged.insert(0, "Consecutivo de fila", range(1, len(df_merged) + 1))
    
    # 5. Rename columns to requested Spanish labels
    column_mapping = {
        "NitDpi": "Nit o DPI",
        "Cliente": "Cliente",
        "Telefono": "Telefono",
        "Celular": "Celular",
        "Email": "email",
        "FechaUltimaCompra": "fecha de ultima compra",
        "DiasSinCompra": "dias sin compra",
        "SegmentoSinCompra": "segmento sin compra",
        "SucursalPreferida": "sucursal preferida",
        "VendedorUltimaFactura": "Vendedor ultima factura",
        "FacturasTotales": "Facturas Totales",
        "UnidadesTotales": "Unidades totales",
        "VentaNetaTotal": "Venta Neta Total",
        "UnidadesFullPrecio": "Unidades Full precio",
        "UnidadesPromocion": "Unidades Promocion",
        "PorcentajeFullPrecio": "PorcentajeFullPrecio",
        "PorcentajePromocion": "ProcentajePromocion",
        "estado_local": "Estado Asignación Local",
        "fecha_asignacion_local": "Fecha Asignación Local"
    }
    df_merged = df_merged.rename(columns=column_mapping)
    return df_merged

def main():
    print("Iniciando generación de reporte CRM - Vía Majadas...")
    try:
        df_merged = get_majadas_crm_dataframe()
        if df_merged.empty:
            print("No se encontraron clientes para Vía Majadas.")
            sys.exit(0)
    except Exception as exc:
        print(f"Error al generar los datos: {exc}")
        sys.exit(1)
        
    # Generate Excel bytes
    sheet_name = "CRM Majadas"
    excel_bytes = dataframe_to_excel_bytes({sheet_name: df_merged})
    
    # Save Excel file
    output_filename = "wally_crm_majadas.xlsx"
    output_path = APP_DIR / output_filename
    
    with open(output_path, "wb") as f:
        f.write(excel_bytes)
        
    print(f"Archivo Excel generado con éxito en: {output_path}")
    print(f"Total registros: {len(df_merged)}")

if __name__ == "__main__":
    main()
