from __future__ import annotations

import sys
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from services import db


CHECKS: list[tuple[str, str]] = [
    (
        "Resumen Ventas",
        f"""
        SELECT
            SUM(ISNULL(VentaNetaQ, 0)) AS VentaNetaQ,
            SUM(ISNULL(Unidades, 0)) AS Unidades,
            COUNT(DISTINCT CASE WHEN Trn = 'FV' THEN Numero END) AS Facturas
        FROM {db.VIEW_VENTAS}
        WHERE CAST(Fecha AS date) = CAST(GETDATE() AS date)
        """,
    ),
    (
        "Gerencia",
        f"""
        SELECT TOP 10 Sucursal, SUM(ISNULL(VentaNetaQ, 0)) AS Venta
        FROM {db.VIEW_VENTAS}
        WHERE Fecha >= DATEADD(day, -30, CAST(GETDATE() AS date))
        GROUP BY Sucursal
        ORDER BY Venta DESC
        """,
    ),
    (
        "Existencias",
        f"""
        SELECT TOP 10 Sucursal, SUM(ISNULL(ExistenciaDisponible, 0)) AS Disponible
        FROM {db.VIEW_EXISTENCIA}
        GROUP BY Sucursal
        ORDER BY Disponible DESC
        """,
    ),
    (
        "Embarques y Coleccion",
        f"""
        WITH Ventas AS (
            SELECT CodEmbarqueAbreviado, SUM(ISNULL(VentaNetaQ, 0)) AS Venta
            FROM {db.VIEW_VENTAS}
            WHERE Fecha >= DATEADD(day, -30, CAST(GETDATE() AS date))
            GROUP BY CodEmbarqueAbreviado
        )
        SELECT TOP 10 *
        FROM Ventas
        ORDER BY Venta DESC
        """,
    ),
    (
        "CRM",
        f"""
        SELECT TOP 10 NumeroCliente, Cliente, DiasSinCompra, VentaNetaTotal
        FROM {db.VIEW_CRM}
        ORDER BY DiasSinCompra DESC, VentaNetaTotal DESC
        """,
    ),
    (
        "Traslados",
        f"""
        SELECT TOP 10 Referencia, Sucursal, ExistenciaDisponible
        FROM {db.VIEW_EXISTENCIA}
        WHERE ISNULL(ExistenciaDisponible, 0) > 0
        ORDER BY ExistenciaDisponible DESC
        """,
    ),
    (
        "Auditoria",
        f"""
        SELECT
            COUNT_BIG(*) AS Documentos,
            SUM(CASE WHEN FlagCambioVendedor = 1 THEN 1 ELSE 0 END) AS CambioVendedor,
            SUM(CASE WHEN FlagCambioTardio = 1 THEN 1 ELSE 0 END) AS CambioTardio,
            SUM(CASE WHEN FlagPosibleNotaCredito = 1 THEN 1 ELSE 0 END) AS NotaCredito
        FROM {db.VIEW_AUDITORIA_CAMBIO_VENDEDOR}
        WHERE Fecha >= DATEADD(day, -7, CAST(GETDATE() AS date))
        """,
    ),
    (
        "Presupuesto",
        f"""
        SELECT TOP 10 Sucursal, SUM(ISNULL(VentaNetaQ, 0)) AS Venta
        FROM {db.VIEW_VENTAS}
        WHERE Fecha >= DATEADD(day, -30, CAST(GETDATE() AS date))
        GROUP BY Sucursal
        ORDER BY Venta DESC
        """,
    ),
    (
        "Reportes",
        f"""
        SELECT TOP 100 Fecha, Sucursal, Numero, VentaNetaQ
        FROM {db.VIEW_VENTAS}
        ORDER BY Fecha DESC
        """,
    ),
]


def main() -> int:
    ok, message = db.test_connection()
    print(f"conexion: {'OK' if ok else 'ERROR'} - {message}")
    if not ok:
        return 1

    failed = False
    for label, query in CHECKS:
        started = time.perf_counter()
        try:
            frame = db.read_sql(query)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            print(f"{label}: OK filas={len(frame)} tiempo_ms={elapsed_ms}")
        except Exception as exc:
            failed = True
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            print(f"{label}: ERROR {type(exc).__name__}: {exc} tiempo_ms={elapsed_ms}")

    try:
        db.read_sql("SELECT TOP 1 * FROM StudioF.dbo.MovimientoInv")
    except PermissionError:
        print("Bloqueo StudioF runtime: OK")
    else:
        failed = True
        print("Bloqueo StudioF runtime: ERROR")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
