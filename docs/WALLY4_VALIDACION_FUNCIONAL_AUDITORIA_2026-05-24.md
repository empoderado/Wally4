# Validacion funcional auditoria - 2026-05-24

## Entorno validado

- Conexion Python/pyodbc correcta contra `WallyBD`.
- SQL Server reportado por la conexion: `AC2D171\SB22`.
- Driver efectivo: `ODBC Driver 17 for SQL Server`.
- StudioF se uso solo en consultas de lectura.

## Resumen de datos reales

Consulta ejecutada el 2026-05-24 13:16 hora del servidor:

| Fecha | Documentos | CambioVendedor | PosteriorPago | PosteriorCierre | CambioTardio | PosibleNotaCredito |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-05-24 | 21 | 0 | 0 | 0 | 2 | 5 |

El conteo difiere del corte previo de 16 documentos porque entraron documentos adicionales durante la jornada.

## AUD-CAMBIO-TARDIO

Casos actuales revisados:

| Numero | idSucursal | idMovimientoInv | idTransaccionInv | Catalogo | idMovimientoInvRef | FlagAnulado | VendedorInicial | VendedorFinalBIT |
| --- | ---: | ---: | ---: | --- | --- | --- | ---: | ---: |
| S008T001592 | 8 | 111600000 | 4 | Exporta a Sucursal | NULL | 0 | 91 | 91 |
| S011T001168 | 11 | 111608000 | 4 | Exporta a Sucursal | NULL | 0 | 124 | 124 |

Hallazgo: `idTransaccionInv = 4` corresponde a `Exporta a Sucursal` en `StudioF.dbo.TransaccionInv`. Los documentos tienen un par de importacion con `idTransaccionInv = 5` (`Importa de Sucursal`) que referencia el movimiento original mediante `idMovimientoInvRef`.

Decision aplicada: `FlagCambioTardio` excluye transacciones 4 y 5 para evitar falsos positivos de transferencia operativa. Impacto medido antes del cambio:

| Rango | Tardio actual | Tardio propuesto |
| --- | ---: | ---: |
| Hoy 2026-05-24 | 2 | 0 |
| Ultimos 90 dias | 452 | 72 |

Validacion post-cambio:

| Numero | idTransaccionInv | Catalogo | MinutosHastaUltimoCambio | FlagCambioTardio |
| --- | ---: | --- | ---: | --- |
| S008T001592 | 4 | Exporta a Sucursal | 904 | 0 |
| S008T001592 | 5 | Importa de Sucursal | 0 | 0 |
| S011T001168 | 4 | Exporta a Sucursal | 66 | 0 |
| S011T001168 | 5 | Importa de Sucursal | 0 | 0 |

## AUD-NOTA-CREDITO

Hallazgo: `idMovimientoInvRef IS NOT NULL` no identifica notas de credito. En los datos de hoy e historicos identifica principalmente importaciones de sucursal (`idTransaccionInv = 5`) con referencia a exportaciones (`idTransaccionInvRef = 4`).

Catalogo validado:

| idTransaccionInv | Descripcion | Sigla |
| ---: | --- | --- |
| 10 | Nota de credito cliente | NCC |

Muestras historicas de notas de credito tienen `idTransaccionInv = 10`, numero con prefijo `NC...`, `NumeroRef` apuntando a factura, y `idMovimientoInvRef` nulo.

Decision aplicada: `FlagPosibleNotaCredito` usa `mov.idTransaccionInv = 10`. Impacto medido antes del cambio:

| Rango | Flag anterior | Flag propuesto |
| --- | ---: | ---: |
| Hoy 2026-05-24 | 5 | 1 |
| Ultimos 90 dias | 1939 | 338 |

Validacion post-cambio del 2026-05-24:

| Documento | idTransaccionInv | Catalogo | idMovimientoInvRef | FlagPosibleNotaCredito |
| --- | ---: | --- | --- | --- |
| S002T004765 | 5 | Importa de Sucursal | 111610000 | 0 |
| S002T004764 | 5 | Importa de Sucursal | 111609000 | 0 |
| S003T004166 | 5 | Importa de Sucursal | 111611000 | 0 |
| S008T001592 | 5 | Importa de Sucursal | 111600000 | 0 |
| S011T001168 | 5 | Importa de Sucursal | 111608000 | 0 |
| NCOAK2 00000087 | 10 | Nota de credito cliente | NULL | 1 |

Resumen post-cambio para el 2026-05-24 a las 13:27 hora del servidor:

| Documentos | CambioVendedor | PosteriorPago | PosteriorCierre | CambioTardio | NotaCredito |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 22 | 0 | 0 | 0 | 0 | 1 |

## AUD-CAMBIO-VENDEDOR

Hallazgo historico: solo se encontraron 7 casos con `FlagCambioVendedor = 1`, todos en `idTransaccionInv = 31` (`Pedido`) entre 2024-02-23 y 2024-09-08.

La comparacion `VendedorInicial != VendedorFinalBIT` es tecnicamente consistente dentro de `BITMovimientoInv`: las secuencias BIT muestran cambios reales de `idEmpleado` y el ultimo valor coincide con `MovimientoInv.idEmpleadoVendedor` en las muestras revisadas.

Decision funcional: negocio confirmo que `Pedido` (`idTransaccionInv = 31`) no debe auditarse. Las banderas de auditoria excluyen pedidos aunque exista diferencia tecnica entre `VendedorInicial` y `VendedorFinalBIT` o eventos BIT posteriores al cierre.

## Clasificacion funcional de alertas

Actualizado el 2026-05-24:

- La vista `dbo.vw_AuditoriaCambioVendedor` expone `TipoAlerta`, `NivelRiesgo` y `EsRiesgoFraude`.
- `NivelRiesgo = Alto`: cambio de vendedor o cambio posterior al pago.
- `NivelRiesgo = Medio`: cambio posterior al cierre o nota de credito relevante por monto/cierre.
- `NivelRiesgo = Bajo`: nota de credito simple o cambio tardio sin senal adicional.
- `NivelRiesgo = Operativo`: traslados entre sucursales `idTransaccionInv IN (4, 5)` sin cambio de vendedor, sin cambio posterior al pago y sin nota de credito.
- `EsRiesgoFraude = 1`: cambio de vendedor, cambio posterior al pago o nota de credito con monto absoluto mayor/igual a Q1000 o posterior al cierre.

## AUD-POST-CIERRE

Decision funcional: `FlagCambioPosteriorCierre` solo aplica cuando hay cambio BIT real despues del cierre de caja de la misma sucursal y fecha del documento.

Regla aplicada:

- Requiere `CantidadCambiosDetectados > 0`.
- Excluye `Pedido` (`idTransaccionInv = 31`).
- Excluye transferencias operativas entre sucursales (`idTransaccionInv IN (4, 5)`).
- Usa `FechaUltimoCambio > FechaUltimoCierre`.

Casos validados:

- `S017T000053`: `NivelRiesgo = Operativo`, `TipoAlerta = Cambio posterior al cierre; Traslado operativo`, `EsRiesgoFraude = 0`.
- `NCOAK2 00000087`: `NivelRiesgo = Medio`, `TipoAlerta = Nota de credito`, `EsRiesgoFraude = 1`.
