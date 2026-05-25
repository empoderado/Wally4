# Cierre pendientes 1-4 - 2026-05-24

## 1. Refresco Mirror estabilizado

Implementado:

- `Admin.RefrescoMirrorLog`
- `Admin.RefrescoMirrorDetalle`
- `10_refresh_mirror_tables.sql` con refresco por tabla, transacciones y validacion de fuente no vacia.
- `07_Refrescar_WallyBD_Mirror.cmd` como comando operativo.

Ultimo refresco validado:

| IdRefresco | Estado | Duracion |
| ---: | --- | ---: |
| 2 | ok | 24 segundos |

Filas finales:

| Tabla | Filas |
| --- | ---: |
| `Mirror.FacturaConImpuesto` | 154976 |
| `Mirror.Existencia` | 9336 |
| `Mirror.EntradasInventario` | 71760 |
| `Mirror.ClienteResumenCRM` | 17049 |
| `Mirror.MovimientoInv` | 106926 |
| `Mirror.BITMovimientoInv` | 207977 |
| `Mirror.MovimientoInvPago` | 75436 |
| `Mirror.MovCajaCierre` | 62289 |
| `Mirror.TransaccionInv` | 45 |

## 2. Indices Mirror creados

Se crearon indices en `WallyBD`, no en `StudioF`.

Tablas cubiertas:

- `Mirror.FacturaConImpuesto`
- `Mirror.Existencia`
- `Mirror.EntradasInventario`
- `Mirror.ClienteResumenCRM`
- `Mirror.MovimientoInv`
- `Mirror.BITMovimientoInv`
- `Mirror.MovimientoInvPago`
- `Mirror.MovCajaCierre`

## 3. Auditoria funcional

Casos registrados en `Audit.CasoValidacionAuditoria`:

| Regla | Estado regla | Casos | Coinciden |
| --- | --- | ---: | ---: |
| `AUD-CAMBIO-TARDIO` | `validacion_tecnica_ok` | 2 | 2 |
| `AUD-NOTA-CREDITO` | `validacion_tecnica_ok` | 3 | 3 |
| `AUD-CAMBIO-VENDEDOR` | `validacion_funcional_ok` | 1 | 1 |

Decision funcional cerrada:

- Cambios de vendedor en `Pedido` (`idTransaccionInv = 31`) no deben auditarse como cambio de vendedor.

Decision funcional cerrada:

- `AUD-POST-CIERRE` requiere cambio BIT real (`CantidadCambiosDetectados > 0`).
- `AUD-POST-CIERRE` excluye pedidos (`idTransaccionInv = 31`) y transferencias operativas (`idTransaccionInv IN (4, 5)`).

## 4. Prueba funcional UX

Script ejecutado:

```powershell
.\.venv\Scripts\python.exe scripts\ux_smoke_queries.py
```

Resultado:

| Modulo | Estado | Tiempo |
| --- | --- | ---: |
| Resumen Ventas | OK | 200 ms |
| Gerencia | OK | 222 ms |
| Existencias | OK | 26 ms |
| Embarques y Coleccion | OK | 8 ms |
| CRM | OK | 6 ms |
| Traslados | OK | 16 ms |
| Auditoria | OK | 385 ms |
| Presupuesto | OK | 13 ms |
| Reportes | OK | 10 ms |

Control de seguridad:

- `SELECT TOP 1 * FROM StudioF.dbo.MovimientoInv`: bloqueado por runtime.

Diagnostico general:

- `scripts/diagnostics.py`: OK.
- `http://127.0.0.1:8504`: HTTP 200 OK.
