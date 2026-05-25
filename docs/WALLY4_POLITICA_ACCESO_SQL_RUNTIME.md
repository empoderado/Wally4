# Politica de acceso SQL runtime - Wally4

## Regla operativa

La app Wally4 en produccion solo debe conectarse a `WallyBD` y consultar vistas autorizadas de esa base. `StudioF` queda como fuente interna para construir/actualizar objetos de `WallyBD`, pero no como destino de consultas del runtime.

## Vistas autorizadas

- `dbo.VwFacturaConImpuesto`
- `dbo.VwExistencia`
- `dbo.VwEntradasInventario`
- `dbo.VwClienteResumenCRM`
- `dbo.vw_AuditoriaCambioVendedor`

## Controles aplicados

- `services.db.connection_string()` exige `SQL_DATABASE=WallyBD` cuando `APP_ENV=production`.
- `services.db.read_sql()` solo acepta `SELECT` o `WITH`.
- Se bloquean instrucciones de escritura o administracion: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `EXEC`, `MERGE`, `TRUNCATE`.
- Se bloquean referencias runtime a `StudioF.`.
- Se bloquean identificadores de tres partes como `Base.Schema.Objeto`.
- Se validan fuentes `FROM`, `JOIN` y `APPLY`: solo pueden apuntar a vistas autorizadas o a CTEs declarados dentro de la consulta.

## Validacion realizada

Fecha: 2026-05-24.

Resultado real:

- Conexion correcta: `AC2D171\SB22 / WallyBD`.
- Consultas exitosas por `db.read_sql()` sobre las cinco vistas autorizadas.
- Consulta directa `SELECT TOP 1 * FROM StudioF.dbo.MovimientoInv`: bloqueada por `PermissionError`.
- Consulta mixta `dbo.VwFacturaConImpuesto JOIN MovimientoInv`: bloqueada por `PermissionError`.
- `dbo.VwEntradasInventario` expone `FechaHoraEntrada` en `WallyBD` como columna derivada de `FechaEntrada` para cumplir el contrato de diagnostico.

## Nota

Los scripts de `database/wallybd` pueden seguir leyendo `StudioF` para crear o actualizar vistas dentro de `WallyBD`. Esa operacion es administrativa, no runtime de la app.
