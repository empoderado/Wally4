# WallyAgent

Nueva app paralela para evolucionar Mar-IA hacia **Mar-IA Agent** sin afectar la app Wally actual.

## Ejecucion local

Requisito recomendado:

- Python 3.12 x64

```powershell
cd C:\Apps\WallyAgent
.\01_Iniciar_o_Reiniciar_Servicios_WallyAgent.cmd
```

URL:

```text
http://127.0.0.1:8503/
```

## WallyAgent 4.0 / Wally

La base inicial de la version 4 vive documentada en:

```text
docs\WALLY4_PLAN.md
```

Los scripts SQL para crear `WallyBD`, las vistas espejo y `dbo.vw_AuditoriaCambioVendedor` estan en:

```text
database\wallybd\
```

Para crear la copia local paralela:

```powershell
cd C:\Apps\WallyAgent
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap_wally4.ps1
```

Esto prepara `C:\Apps\Wally4`, puerto `8504`, base `WallyBD` y SQLite persistente en `C:\ProgramData\Wally4\wally_agent.sqlite`.

En el servidor, despues de copiar la carpeta y confirmar el `.env`, se pueden crear los objetos SQL con:

```powershell
cd C:\Apps\Wally4
.\06_Crear_WallyBD.cmd
.\04_Validar_Modo_Datos_Reales_Wally4.cmd
.\01_Iniciar_o_Reiniciar_Servicios_Wally4.cmd
```

## Mar-IA por Telegram

Configure en `.env`:

```env
TELEGRAM_BOT_TOKEN=PEGUE_AQUI_EL_TOKEN
TELEGRAM_ALLOWED_CHAT_IDS=
```

Si `TELEGRAM_ALLOWED_CHAT_IDS` queda vacio, cualquier chat que encuentre el bot podra consultar. Para restringirlo, coloque los IDs separados por coma.

Ejecute el mismo script de servicios. Este inicia WallyAgent Web y Mar-IA Telegram si el token esta configurado:

```powershell
cd C:\Apps\WallyAgent
.\01_Iniciar_o_Reiniciar_Servicios_WallyAgent.cmd
```

El bot usa el mismo orquestador de Mar-IA Agent, por eso respeta memoria, entrenamiento semantico y SQL seguro.

## Scripts para servidor

Ejecutar desde `C:\Apps\WallyAgent`:

```powershell
.\01_Iniciar_o_Reiniciar_Servicios_WallyAgent.cmd
.\02_Detener_Servicios_WallyAgent.cmd
.\03_Diagnostico_WallyAgent.cmd
.\04_Validar_Modo_Datos_Reales.cmd
.\05_Crear_Acceso_Directo_WallyAgent.cmd
```

`01_Iniciar_o_Reiniciar_Servicios_WallyAgent.cmd` concentra la operacion principal:

- Crea o actualiza la tarea programada.
- Elimina tareas obsoletas de WallyAgent.
- Crea el entorno virtual si falta.
- Actualiza dependencias.
- Si los servicios estan detenidos, los inicia.
- Si los servicios estan activos, los detiene y reinicia limpio.
- Inicia WallyAgent Web y los canales conectados, actualmente Mar-IA Telegram.

La tarea programada se crea en la carpeta visual:

```text
Biblioteca del Programador de tareas\ServiciosWallyAgent
```

Por seguridad con `Trusted_Connection=yes`, la tarea se crea al iniciar sesion del usuario actual. Asi WallyAgent usa las credenciales Windows del usuario que ya tiene permisos sobre SQL Server.

## Icono y acceso directo

El icono oficial de WallyAgent queda guardado en:

```text
C:\Apps\WallyAgent\assets\WallyAgent_icon.png
C:\Apps\WallyAgent\assets\WallyAgent_icon.ico
```

Para crear o actualizar el acceso directo del escritorio con este icono:

```powershell
cd C:\Apps\WallyAgent
.\05_Crear_Acceso_Directo_WallyAgent.cmd
```

## .env recomendado para servidor

```env
SQL_SERVER=NAZGUL\SB22
SQL_DATABASE=WallyBD
SQL_USERNAME=
SQL_PASSWORD=
SQL_DRIVER=ODBC Driver 17 for SQL Server
SQL_TRUSTED_CONNECTION=yes
APP_PORT=8503
APP_HOST=127.0.0.1
APP_ENV=production
USE_MOCK_DATA=no
WALLY_AGENT_SQLITE_PATH=C:\ProgramData\WallyAgent\wally_agent.sqlite

MARIA_AGENT_PROVIDER=openai
MARIA_AGENT_MODEL=gpt-5.5
MARIA_AGENT_BASE_URL=
MARIA_AGENT_API_KEY=
MARIA_AGENT_BACKUP_PROVIDER=openai
MARIA_AGENT_BACKUP_MODEL=gpt-4.1-mini
MARIA_AGENT_BACKUP_BASE_URL=
MARIA_AGENT_BACKUP_API_KEY=

TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_CHAT_IDS=
```

## Principios

- Wally4 se conecta a `WallyBD`; la app no consulta `StudioF` directamente.
- Mar-IA Agent solo puede ejecutar consultas `SELECT` sobre vistas autorizadas de `WallyBD`.
- La memoria, entrenamiento, tareas, feedback y configuracion viven en SQLite local.
- Traslados FIFO-XLS genera sugerencias de cruce de mercancia desde `dbo.VwExistencia`; no modifica el ERP.
- Toda comunicacion de usuario debe estar en espanol.
- Wally actual en `C:\Apps\Wally` no se modifica para esta nueva app.

## Datos locales persistentes

La base local de WallyAgent debe vivir fuera de la carpeta de codigo para no perder presupuesto, memoria local, entrenamiento, CRM ni configuracion al reemplazar `C:\Apps\WallyAgent`.

Ruta recomendada:

```text
C:\ProgramData\WallyAgent\wally_agent.sqlite
```

Para copiar los datos locales hacia otro equipo o servidor:

```powershell
cd C:\Apps\WallyAgent
.\scripts\backup_local_data.ps1
```

Para restaurar esa copia en el servidor:

```powershell
cd C:\Apps\WallyAgent
.\scripts\restore_local_data.ps1 -SourceSqlite "RUTA_DEL_BACKUP.sqlite"
```
