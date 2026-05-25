# WallyAgent 4.0 - Base inicial

## Objetivo

Crear una version paralela llamada Wally, instalada en `C:\Apps\Wally4`, que use la base empresarial `WallyBD` y escuche en:

```text
http://127.0.0.1:8504/
```

La version actual en `C:\Apps\WallyAgent` y `http://127.0.0.1:8503/` debe seguir operando como referencia.

## Principios

- `StudioF` queda solo lectura.
- Nuevas vistas, tablas historicas, ETL y objetos de auditoria viven en `WallyBD`.
- WallyAgent V4 apunta a `WallyBD` mediante `SQL_DATABASE=WallyBD`.
- Las vistas espejo en `WallyBD.dbo` conservan nombres compatibles con la app actual.

## Orden de ejecucion SQL

Ejecutar en SQL Server Management Studio con un usuario autorizado:

1. `database/wallybd/00_create_wallybd.sql`
2. `database/wallybd/01_create_mirror_views.sql`
3. `database/wallybd/02_create_vw_AuditoriaCambioVendedor.sql`
4. `database/wallybd/03_smoke_tests.sql`
5. `database/wallybd/05_validar_contrato_wallybd.sql`
6. `database/wallybd/06_create_audit_validation_tables.sql`
7. `database/wallybd/07_seed_audit_validation_rules.sql`

Si `FlagCambioPosteriorCierre` sale demasiado alto o bajo, ejecutar manualmente:

```text
database/wallybd/04_diagnostico_cierre_auditoria.sql
```

Los indices recomendados sobre `StudioF` estan documentados al final del script 02, pero no se ejecutan automaticamente porque modifican el ERP productivo.

El contrato tecnico de vistas y columnas esta documentado en:

```text
database/wallybd/README.md
docs/WALLY4_FASES.md
```

Las consultas manuales para validar reglas en el ambiente real quedan en:

```text
database/wallybd/08_consultas_validacion_reglas_auditoria.sql
```

## Bootstrap local

Desde `C:\Apps\WallyAgent`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap_wally4.ps1
```

El script crea o actualiza `C:\Apps\Wally4`, copia el codigo sin `.git`, `.venv`, logs ni caches, y deja `.env` basado en `.env.v4.example`.
Si `C:\Apps\Wally4\.env` ya existe, lo preserva para no borrar credenciales reales. Para regenerarlo usar:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap_wally4.ps1 -ResetEnv
```

## Validaciones

Despues de crear los objetos SQL:

```powershell
cd C:\Apps\Wally4
.\06_Crear_WallyBD.cmd
.\04_Validar_Modo_Datos_Reales_Wally4.cmd
.\01_Iniciar_o_Reiniciar_Servicios_Wally4.cmd
```

Luego abrir:

```text
http://127.0.0.1:8504/
```
