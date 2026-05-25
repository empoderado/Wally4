# Fase 3 - Reportes ejecutivos de auditoria - 2026-05-24

## Implementado

El modulo `Auditoria` usa `dbo.vw_AuditoriaCambioVendedor` como unica fuente autorizada para la UX.

Vistas agregadas:

- Resumen ejecutivo por nivel de riesgo.
- Ranking por usuario modificador.
- Ranking especifico de usuarios con mas cambios de vendedor.
- Ranking por sucursal.
- Detalle filtrable de alertas con comentario explicativo.
- Exportacion Excel con hojas de resumen, riesgo, usuarios, cambios de vendedor, sucursales y detalle.

## Reglas consideradas

- `Pedido` (`idTransaccionInv = 31`) no se audita.
- `AUD-POST-CIERRE` requiere cambio BIT real (`CantidadCambiosDetectados > 0`).
- Transferencias operativas (`idTransaccionInv IN (4, 5)`) quedan fuera de `AUD-POST-CIERRE`.
- El ranking de cambios de vendedor solo cuenta `FlagCambioVendedor = 1`.

## Validacion

```text
python -m compileall modules/auditoria.py: OK
scripts/diagnostics.py: OK
scripts/ux_smoke_queries.py: OK
consultas ejecutivas directas: OK
```

Resultado de validacion directa con rango 2026-05-24:

| Consulta | Filas |
| --- | ---: |
| Resumen | 1 |
| Ranking usuarios | 2 |
| Ranking sucursales | 2 |
| Ranking cambios de vendedor | 0 |
| Composicion riesgo | 2 |

El ranking de cambios de vendedor queda sin filas para el rango validado porque no hay cambios de vendedor auditables despues de excluir pedidos por decision funcional.
