# Validacion aislamiento WallyBD - 2026-05-24

## Regla objetivo

La aplicacion UX de Wally4 debe consultar solo objetos de `WallyBD`. `StudioF` queda como fuente permitida solo para procesos administrativos de alimentacion/actualizacion de tablas dentro de `WallyBD`.

## Ejecutado

1. Se mantuvo el contrato publico de vistas `dbo.Vw*`.
2. Se crearon tablas materializadas `Mirror.*` en `WallyBD`.
3. Se agrego proceso administrativo de refresco desde tablas base de `StudioF`: `Source.*`, `10_refresh_mirror_tables.sql` y `07_Refrescar_WallyBD_Mirror.cmd`.
4. Se actualizaron las vistas publicas para leer `Mirror.*`.
5. No se revocaron permisos de `StudioF`; ese punto queda para otra fecha.
6. Se ejecuto diagnostico de contrato y dependencias.

## Tablas Mirror cargadas

| Tabla | Filas aproximadas |
| --- | ---: |
| `Mirror.BITMovimientoInv` | 207993 |
| `Mirror.ClienteResumenCRM` | 17048 |
| `Mirror.EntradasInventario` | 71760 |
| `Mirror.Existencia` | 9334 |
| `Mirror.FacturaConImpuesto` | 154983 |
| `Mirror.MovCajaCierre` | 62289 |
| `Mirror.MovimientoInv` | 106933 |
| `Mirror.MovimientoInvPago` | 75440 |
| `Mirror.TransaccionInv` | 45 |

## Dependencias actuales de vistas publicas

| Vista publica | Fuente actual |
| --- | --- |
| `dbo.VwFacturaConImpuesto` | `Mirror.FacturaConImpuesto` |
| `dbo.VwExistencia` | `Mirror.Existencia` |
| `dbo.VwEntradasInventario` | `Mirror.EntradasInventario` |
| `dbo.VwClienteResumenCRM` | `Mirror.ClienteResumenCRM` |
| `dbo.vw_AuditoriaCambioVendedor` | `Mirror.MovimientoInv`, `Mirror.BITMovimientoInv`, `Mirror.MovimientoInvPago`, `Mirror.MovCajaCierre`, `Mirror.TransaccionInv` |

## Diagnostico post-cambio

- Conexion: `AC2D171\SB22 / WallyBD`.
- `dbo.VwClienteResumenCRM`: OK, contrato completo.
- `dbo.VwEntradasInventario`: OK, contrato completo.
- `dbo.VwExistencia`: OK, contrato completo.
- `dbo.VwFacturaConImpuesto`: OK, contrato completo.
- `dbo.vw_AuditoriaCambioVendedor`: OK.

## Conclusion

Los reportes UX quedan consultando vistas publicas en `WallyBD`; esas vistas ya no dependen directamente de `StudioF`, sino de tablas `Mirror.*` dentro de `WallyBD`. La lectura de `StudioF` queda concentrada en el proceso administrativo de refresco.

Actualizacion posterior: el refresco de ventas, existencia, entradas y CRM ya no depende de vistas `StudioF.dbo.Vw*`; usa vistas `WallyBD.Source.*` construidas sobre tablas base de `StudioF`.

## Validacion posterior contra eliminacion de vistas StudioF

Ejecutado el 2026-05-24 15:25:

- `09b_create_source_views_from_studiof_tables.sql`: OK.
- `10_refresh_mirror_tables.sql`: OK, `IdRefresco=25`, duracion 25 segundos.
- Tarea programada `\ServiciosWally4\Refrescar WallyBD Mirror`: OK, `IdRefresco=26`, duracion 27 segundos, ultimo resultado `0`, proxima ejecucion 15:30.
- `dbo.VwFacturaConImpuesto`, `dbo.VwExistencia`, `dbo.VwEntradasInventario`, `dbo.VwClienteResumenCRM`: dependen solo de `Mirror.*`.
- `dbo.vw_AuditoriaCambioVendedor`: depende solo de `Mirror.*`.
- `Source.VwFacturaConImpuesto`, `Source.VwExistencia`, `Source.VwEntradasInventario`, `Source.VwClienteResumenCRM`: dependen de tablas base `StudioF.dbo.*`, no de vistas `StudioF.dbo.Vw*`.
- Dependencias detectadas a vistas `StudioF.dbo.Vw*`: 0.
- Smoke UX: OK.
- App HTTP `http://127.0.0.1:8504`: 200.
