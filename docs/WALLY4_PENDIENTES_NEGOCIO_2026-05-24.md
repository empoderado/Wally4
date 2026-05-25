# Pendientes funcionales de negocio - Wally4 - 2026-05-24

## Estado tecnico actual

- App Wally4 operativa en `http://127.0.0.1:8504/`.
- `APP_ENV=production` y `USE_MOCK_DATA=no`.
- SQLite persistente operativo en `C:\ProgramData\Wally4\wally_agent.sqlite`.
- Conexion SQL validada contra `AC2D171\SB22 / WallyBD`.
- Contrato de vistas autorizado validado.
- Smoke UX con datos reales validado.
- Bloqueo runtime a consultas directas contra `StudioF` validado.

## Decisiones funcionales

### 1. AUD-CAMBIO-VENDEDOR en pedidos

Estado: cerrado.

Contexto validado:

- Los casos historicos encontrados con `FlagCambioVendedor = 1` corresponden a `idTransaccionInv = 31`.
- La comparacion tecnica entre `VendedorInicial` y `VendedorFinalBIT` es consistente.

Decision:

- `Pedido` no debe auditarse como cambio de vendedor.
- Las banderas de auditoria excluyen `idTransaccionInv = 31`.
- El caso historico de pedido queda como validacion funcional esperada en `0`.

### 2. AUD-POST-CIERRE

Estado: cerrado como regla funcional inicial.

Contexto validado:

- La vista expone `FlagCambioPosteriorCierre`.
- La clasificacion actual considera riesgo medio cuando hay cambio posterior al cierre sin senales mas fuertes.

Decision:

- Requiere cambio BIT real: `CantidadCambiosDetectados > 0`.
- Excluye `Pedido` (`idTransaccionInv = 31`).
- Excluye transferencias operativas entre sucursales (`idTransaccionInv IN (4, 5)`).
- Usa el ultimo cierre de caja de la misma sucursal y fecha del documento.

### 3. Reportes ejecutivos de auditoria

La Fase 3 puede iniciar con estas reglas funcionales cerradas.

Reportes propuestos:

- Resumen por usuario modificador.
- Resumen por sucursal.
- Ranking por monto auditado.
- Exportacion Excel ejecutiva con resumen, detalle, usuarios y sucursales.

## Validacion ejecutada

```text
scripts/diagnostics.py: OK
scripts/validate_real_data_mode.py: OK
python -m compileall app.py services modules agents scripts: OK
scripts/ux_smoke_queries.py: OK
http://127.0.0.1:8504/: HTTP 200 OK
```

Resultado smoke UX:

| Modulo | Estado |
| --- | --- |
| Resumen Ventas | OK |
| Gerencia | OK |
| Existencias | OK |
| Embarques y Coleccion | OK |
| CRM | OK |
| Traslados | OK |
| Auditoria | OK |
| Presupuesto | OK |
| Reportes | OK |
| Bloqueo StudioF runtime | OK |
