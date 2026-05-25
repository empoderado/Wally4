# WallyBD

## Contrato inicial

`WallyBD` es la base empresarial de WallyAgent V4. El ERP `StudioF` se mantiene como fuente productiva de solo lectura.

Objetos iniciales:

- `Mirror.FacturaConImpuesto`: tabla materializada desde `StudioF` para ventas.
- `Mirror.Existencia`: tabla materializada desde `StudioF` para existencias.
- `Mirror.EntradasInventario`: tabla materializada desde `StudioF` para entradas.
- `Mirror.ClienteResumenCRM`: tabla materializada desde `StudioF` para CRM.
- `Mirror.MovimientoInv`, `Mirror.BITMovimientoInv`, `Mirror.MovimientoInvPago`, `Mirror.MovCajaCierre`, `Mirror.TransaccionInv`: tablas materializadas para auditoria.
- `Source.VwFacturaConImpuesto`, `Source.VwExistencia`, `Source.VwEntradasInventario`, `Source.VwClienteResumenCRM`: vistas internas de alimentacion construidas sobre tablas base de `StudioF`, sin depender de vistas `StudioF.dbo.Vw*`.
- `dbo.VwFacturaConImpuesto`: vista publica para la app, lee `Mirror.FacturaConImpuesto`.
- `dbo.VwExistencia`: vista publica para la app, lee `Mirror.Existencia`.
- `dbo.VwEntradasInventario`: vista publica para la app, lee `Mirror.EntradasInventario`.
- `dbo.VwClienteResumenCRM`: vista publica para la app, lee `Mirror.ClienteResumenCRM`.
- `dbo.vw_AuditoriaCambioVendedor`: vista analitica de auditoria sobre cambios de vendedor, cambios posteriores al pago/cierre y notas credito.

## Scripts

1. `00_create_wallybd.sql`: crea `WallyBD` y esquema `Audit`.
2. `09_create_mirror_tables.sql`: crea tablas materializadas `Mirror.*` en `WallyBD`.
3. `09b_create_source_views_from_studiof_tables.sql`: crea vistas internas `Source.*` desde tablas base de `StudioF`.
4. `09a_create_admin_refresh_log.sql`: crea bitacora administrativa de refrescos.
5. `10_refresh_mirror_tables.sql`: refresca tablas `Mirror.*` desde `Source.*` y tablas base de auditoria, con transacciones y bitacora.
6. `11_create_mirror_indexes.sql`: crea indices de rendimiento en `Mirror.*`.
7. `01_create_mirror_views.sql`: crea vistas publicas compatibles con la app actual, leyendo `Mirror.*`.
8. `02_create_vw_AuditoriaCambioVendedor.sql`: crea la vista de auditoria.
9. `03_smoke_tests.sql`: consultas rapidas de validacion.
10. `04_diagnostico_cierre_auditoria.sql`: diagnostico manual para regla posterior al cierre.
11. `05_validar_contrato_wallybd.sql`: valida existencia de vistas y columnas esperadas.
12. `06_create_audit_validation_tables.sql`: crea tablas de validacion funcional en `Audit`.
13. `07_seed_audit_validation_rules.sql`: registra las reglas iniciales a validar.
14. `08_consultas_validacion_reglas_auditoria.sql`: consultas manuales para revisar reglas y datos reales.
15. `12_seed_audit_validation_cases.sql`: registra casos reales ya revisados.

## Refresco administrativo

Para refrescar las tablas `Mirror.*` desde `StudioF` sin cambiar el contrato publico:

```powershell
cd C:\Apps\Wally4
.\07_Refrescar_WallyBD_Mirror.cmd
```

La app UX no consulta `StudioF`; consulta las vistas `dbo.*` dentro de `WallyBD`. El refresco administrativo no depende de vistas `StudioF.dbo.Vw*`; lee tablas base por medio de `WallyBD.Source.*`.

Para validar consultas representativas de la UX:

```powershell
cd C:\Apps\Wally4
.\.venv\Scripts\python.exe scripts\ux_smoke_queries.py
```

## Reglas actuales de auditoria

- Las banderas de auditoria excluyen pedidos (`idTransaccionInv = 31`) por decision funcional de negocio.
- `FlagCambioVendedor`: compara primer vendedor historico contra ultimo vendedor historico en `BITMovimientoInv`.
- `FlagCambioPosteriorPago`: ultimo cambio mas de 60 segundos despues de `FechaUltimoPago`.
- `FlagCambioPosteriorCierre`: `FechaUltimoCambio > FechaUltimoCierre`, usando cierre de la misma fecha del documento y sucursal; requiere `CantidadCambiosDetectados > 0` y excluye transferencias operativas.
- `FlagCambioTardio`: ultimo cambio mas de 60 minutos despues del primer registro BIT, excluyendo transferencias operativas entre sucursales (`idTransaccionInv` 4 y 5).
- `FlagPosibleNotaCredito`: `idTransaccionInv = 10` (`Nota de credito cliente` en `StudioF.dbo.TransaccionInv`).

## Pendientes de confirmacion funcional

- Confirmar si `BITMovimientoInv.idEmpleado` representa vendedor historico.
- Confirmar con facturas reales una muestra de alertas y no-alertas antes de congelar la vista como estable.
- Revisar si reglas de cambio tardio deben limitarse a factura/pedido o si tambien deben incluir otras transacciones no-transferencia.

## Tablas de validacion

Las tablas `Audit.ReglaAuditoria` y `Audit.CasoValidacionAuditoria` viven en `WallyBD`.
Se usan para validar reglas contra documentos reales en el servidor, sin crear objetos en `StudioF`.
