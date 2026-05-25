# WallyAgent V4 - Plan por fases

## Fase 1 - Auditoria SQL

Estado: en validacion con datos reales.

Pasos:

1. Aplicar `database/wallybd/02_create_vw_AuditoriaCambioVendedor.sql` en servidor.
2. Ejecutar `database/wallybd/03_smoke_tests.sql`.
3. Revisar que `FlagCambioPosteriorCierre` no marque 100% sin justificacion.
4. Validar 5 a 10 facturas reales contra SmartBit.
5. Confirmar significado funcional de `BITMovimientoInv.idEmpleado`.

Salida esperada:

- Vista de auditoria estable para V4.
- Reglas confirmadas o documentadas como supuestos.

## Fase 2 - Branding e interfaz base

Estado: aplicado en codigo.

Pasos:

1. Usar `APP_NAME=Wally4` en `.env.v4.example`.
2. Mostrar nombre de app desde `.env` en titulo del navegador y sidebar.
3. Mantener `WallyAgent` como fallback para la version 8503.
4. Mostrar base SQL y puerto activos en sidebar.

Salida esperada:

- `8503` y `8504` diferenciados visualmente.
- V4 identificada como Wally4 sin romper la app anterior.

## Fase 4 - WallyBD

Estado: en construccion como ambiente final de validacion SQL.

Pasos:

1. Mantener vistas espejo iniciales en `WallyBD.dbo`.
2. Mantener auditoria en `WallyBD.dbo.vw_AuditoriaCambioVendedor`.
3. Validar contrato con `05_validar_contrato_wallybd.sql`.
4. Crear tablas de validacion con `06_create_audit_validation_tables.sql`.
5. Registrar reglas iniciales con `07_seed_audit_validation_rules.sql`.
6. Ejecutar consultas funcionales con `08_consultas_validacion_reglas_auditoria.sql`.
7. Evaluar indices recomendados con DBA antes de tocar `StudioF`.
8. Definir si el historico vivira en `Audit.AuditoriaCambioVendedorHistorico`.

Salida esperada:

- `WallyBD` como capa estable entre SmartBit y Wally4.
- Base lista para validar reglas con datos reales antes de Fase 3 de reportes.

## Fase 3 - Reportes de auditoria

Estado: postergada hasta cerrar Fase 4.

Pasos futuros:

1. Resumen por usuario modificador.
2. Resumen por sucursal.
3. Ranking por monto auditado.
4. Excel ejecutivo con resumen, detalle, usuarios y sucursales.
