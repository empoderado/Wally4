from __future__ import annotations

import sqlite3
from datetime import datetime

import pandas as pd

from services.paths import ensure_dirs, sqlite_path


DEFAULT_AGENT_PROMPT = """Eres Mar-IA Agent, copiloto ejecutivo de Wally para retail.
Responde siempre en espanol.
Usa solo informacion autorizada de Wally, sus vistas, reportes y memoria local.
No inventes datos. Si falta informacion, dilo y pide aclaracion.
SQL Server operativo es WallyBD. Nunca sugieras ni ejecutes consultas directas sobre el ERP StudioF.
Si una accion requiere aprobacion humana, solicitala antes de ejecutarla."""

DEFAULT_CALL_QUOTA = 60
DEFAULT_MARIA_PERSONALITY_PROMPT = """Eres Mar-IA, asistente comercial de Wally para retail.
Responde en espanol, con criterio gerencial, breve y accionable.
Solo puedes usar informacion de las vistas permitidas de Wally y reportes calculados por la app.
No inventes datos. Si no tienes datos suficientes, dilo.
No puedes modificar bases de datos, crear registros, enviar mensajes comerciales ni ejecutar SQL libre.
No respondas preguntas por fuera de Wally, sus vistas, reportes, indicadores, CRM, inventario, ventas, metas o configuracion.
Si propones acciones gerenciales, deben ser concretas. Si son varias, numeralas desde 1."""


DEFAULT_SEMANTIC_TERMS = [
    ("stock", "existencia fisica y disponible de inventario", "inventario,existencia,existencias", 1),
    ("tienda", "sucursal comercial", "sucursal,punto de venta,local", 1),
    ("asesora", "vendedor o vendedora responsable de la venta", "vendedor,vendedora,asesor", 1),
    ("facturacion", "venta neta en quetzales filtrada por facturas FV", "venta,ventas,venta neta,venta real", 1),
    ("producto", "referencia, linea, tipo de prenda o articulo", "referencia,linea,tipo prenda,articulo", 1),
    ("embarque", "codigo de embarque de mercancia", "codembarque,codembarqueabreviado,coleccion", 1),
    ("rotacion", "relacion entre unidades facturadas y unidades entradas", "porcentaje de rotacion,% rotacion,%rot", 1),
]


def connect() -> sqlite3.Connection:
    ensure_dirs()
    path = sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_store() -> None:
    conn = connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_parametros (
                clave TEXT PRIMARY KEY,
                valor TEXT NOT NULL,
                descripcion TEXT,
                actualizado_en TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS maria_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL,
                user_id TEXT,
                user_name TEXT,
                question TEXT NOT NULL,
                answer TEXT,
                intent TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS maria_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_type TEXT NOT NULL,
                key_text TEXT NOT NULL,
                value_text TEXT NOT NULL,
                user_id TEXT,
                expires_at TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS semantic_dictionary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                term TEXT NOT NULL UNIQUE,
                definition TEXT NOT NULL,
                aliases TEXT,
                approved INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS training_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                expected_intent TEXT,
                expected_response TEXT,
                approved INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agent_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT NOT NULL,
                payload TEXT,
                status TEXT NOT NULL DEFAULT 'Pendiente',
                requires_approval INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS crm_asignaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha_asignacion TEXT NOT NULL,
                nit_dpi TEXT NOT NULL,
                cliente TEXT NOT NULL,
                sucursal_preferida TEXT,
                vendedor_responsable TEXT,
                estado TEXT NOT NULL DEFAULT 'Pendiente',
                aprobado INTEGER NOT NULL DEFAULT 0,
                creado_en TEXT NOT NULL,
                UNIQUE(fecha_asignacion, nit_dpi)
            );

            CREATE TABLE IF NOT EXISTS crm_gestiones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asignacion_id INTEGER,
                nit_dpi TEXT NOT NULL,
                resultado TEXT NOT NULL,
                observacion TEXT,
                proxima_llamada TEXT,
                vendedor_responsable TEXT,
                usuario TEXT,
                creado_en TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS meta_sucursal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anio INTEGER NOT NULL,
                mes INTEGER NOT NULL,
                sucursal TEXT NOT NULL,
                meta_venta_q REAL NOT NULL DEFAULT 0,
                meta_unidades REAL NOT NULL DEFAULT 0,
                meta_facturas REAL NOT NULL DEFAULT 0,
                creado_en TEXT NOT NULL,
                UNIQUE(anio, mes, sucursal)
            );

            CREATE TABLE IF NOT EXISTS meta_vendedor (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anio INTEGER NOT NULL,
                mes INTEGER NOT NULL,
                sucursal TEXT,
                id_vendedor TEXT,
                vendedor TEXT NOT NULL,
                meta_venta_q REAL NOT NULL DEFAULT 0,
                meta_unidades REAL NOT NULL DEFAULT 0,
                meta_facturas REAL NOT NULL DEFAULT 0,
                creado_en TEXT NOT NULL,
                UNIQUE(anio, mes, vendedor)
            );

            CREATE TABLE IF NOT EXISTS meta_linea (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anio INTEGER NOT NULL,
                mes INTEGER NOT NULL,
                linea TEXT NOT NULL,
                meta_venta_q REAL NOT NULL DEFAULT 0,
                meta_unidades REAL NOT NULL DEFAULT 0,
                creado_en TEXT NOT NULL,
                UNIQUE(anio, mes, linea)
            );

            CREATE TABLE IF NOT EXISTS pto_sucursal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_sucursal TEXT NOT NULL,
                nombre_sucursal TEXT NOT NULL,
                fecha TEXT NOT NULL,
                unidades REAL NOT NULL DEFAULT 0,
                valor_presupuesto REAL NOT NULL DEFAULT 0,
                anio INTEGER NOT NULL,
                mes INTEGER NOT NULL,
                dia INTEGER NOT NULL,
                dia_semana TEXT NOT NULL,
                semana_mes INTEGER NOT NULL,
                semana_inicio TEXT NOT NULL,
                semana_fin TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(codigo_sucursal, fecha)
            );

            CREATE TABLE IF NOT EXISTS pto_vendedor (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_vendedor TEXT NOT NULL,
                nombre_vendedor TEXT NOT NULL,
                id_sucursal TEXT NOT NULL,
                nombre_sucursal TEXT NOT NULL,
                fecha TEXT NOT NULL,
                unidades REAL NOT NULL DEFAULT 0,
                vr_presupuesto REAL NOT NULL DEFAULT 0,
                anio INTEGER NOT NULL,
                mes INTEGER NOT NULL,
                dia INTEGER NOT NULL,
                dia_semana TEXT NOT NULL,
                semana_mes INTEGER NOT NULL,
                semana_inicio TEXT NOT NULL,
                semana_fin TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(id_vendedor, id_sucursal, fecha)
            );

            CREATE TABLE IF NOT EXISTS pto_linea_sucursal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                id_linea TEXT NOT NULL,
                linea TEXT NOT NULL,
                unidades REAL NOT NULL DEFAULT 0,
                venta_q REAL NOT NULL DEFAULT 0,
                id_sucursal TEXT NOT NULL,
                sucursal TEXT NOT NULL,
                anio INTEGER NOT NULL,
                mes INTEGER NOT NULL,
                dia INTEGER NOT NULL,
                dia_semana TEXT NOT NULL,
                semana_mes INTEGER NOT NULL,
                semana_inicio TEXT NOT NULL,
                semana_fin TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(fecha, id_linea, id_sucursal)
            );

            CREATE TABLE IF NOT EXISTS presupuesto_importacion_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo_importacion TEXT NOT NULL,
                nombre_archivo TEXT,
                total_filas INTEGER NOT NULL DEFAULT 0,
                filas_insertadas INTEGER NOT NULL DEFAULT 0,
                filas_actualizadas INTEGER NOT NULL DEFAULT 0,
                filas_error INTEGER NOT NULL DEFAULT 0,
                usuario TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS presupuesto_importacion_error (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                importacion_id INTEGER NOT NULL,
                numero_fila INTEGER NOT NULL,
                mensaje_error TEXT NOT NULL,
                data_original TEXT,
                FOREIGN KEY(importacion_id) REFERENCES presupuesto_importacion_log(id)
            );

            CREATE TABLE IF NOT EXISTS traslado_prioridad_sucursal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sucursal TEXT NOT NULL UNIQUE,
                prioridad INTEGER NOT NULL DEFAULT 0,
                actualizado_en TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_pto_sucursal_fecha ON pto_sucursal(fecha);
            CREATE INDEX IF NOT EXISTS idx_pto_sucursal_codigo_fecha ON pto_sucursal(codigo_sucursal, fecha);
            CREATE INDEX IF NOT EXISTS idx_pto_sucursal_anio_mes ON pto_sucursal(anio, mes);
            CREATE INDEX IF NOT EXISTS idx_pto_vendedor_fecha ON pto_vendedor(fecha);
            CREATE INDEX IF NOT EXISTS idx_pto_vendedor_id_fecha ON pto_vendedor(id_vendedor, fecha);
            CREATE INDEX IF NOT EXISTS idx_pto_vendedor_sucursal_fecha ON pto_vendedor(id_sucursal, fecha);
            CREATE INDEX IF NOT EXISTS idx_pto_vendedor_anio_mes ON pto_vendedor(anio, mes);
            CREATE INDEX IF NOT EXISTS idx_pto_linea_sucursal_fecha ON pto_linea_sucursal(fecha);
            CREATE INDEX IF NOT EXISTS idx_pto_linea_sucursal_linea_fecha ON pto_linea_sucursal(linea, fecha);
            CREATE INDEX IF NOT EXISTS idx_pto_linea_sucursal_sucursal_fecha ON pto_linea_sucursal(sucursal, fecha);
            """
        )
        set_default_param("maria_agent_prompt", DEFAULT_AGENT_PROMPT, "Prompt base editable de Mar-IA Agent", conn)
        set_default_param("crm_cuota_diaria_vendedor", str(DEFAULT_CALL_QUOTA), "Cuota diaria igual para todos los vendedores", conn)
        set_default_param("maria_ai_provider", "openai", "Proveedor principal de IA para Mar-IA", conn)
        set_default_param("maria_model", "gpt-5.5", "Modelo principal de IA para Mar-IA", conn)
        set_default_param("maria_base_url", "", "URL base opcional del proveedor principal de Mar-IA", conn)
        set_default_param("maria_api_key", "", "API key principal de Mar-IA", conn)
        set_default_param("maria_backup_provider", "openai", "Proveedor secundario de IA para Mar-IA", conn)
        set_default_param("maria_backup_model", "gpt-4.1-mini", "Modelo secundario de IA para Mar-IA", conn)
        set_default_param("maria_backup_base_url", "", "URL base opcional del proveedor secundario de Mar-IA", conn)
        set_default_param("maria_backup_api_key", "", "API key secundaria de Mar-IA", conn)
        set_default_param("maria_transcription_provider", "openai", "Proveedor principal de transcripcion de audio", conn)
        set_default_param("maria_transcription_model", "whisper-1", "Modelo principal de transcripcion de audio", conn)
        set_default_param("maria_local_transcription_enabled", "yes", "Activar respaldo local con faster-whisper", conn)
        set_default_param("maria_local_transcription_model", "small", "Modelo local de faster-whisper", conn)
        set_default_param("maria_personality_prompt", DEFAULT_MARIA_PERSONALITY_PROMPT, "Prompt editable de personalidad y reglas de Mar-IA", conn)
        seed_semantic_dictionary(conn)
        conn.commit()
    finally:
        conn.close()


def init_local_store() -> None:
    init_store()


def set_default_param(clave: str, valor: str, descripcion: str, conn: sqlite3.Connection | None = None) -> None:
    own_conn = conn is None
    conn = conn or connect()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO app_parametros (clave, valor, descripcion, actualizado_en) VALUES (?, ?, ?, ?)",
            (clave, valor, descripcion, datetime.now().isoformat(timespec="seconds")),
        )
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            conn.close()


def seed_semantic_dictionary(conn: sqlite3.Connection | None = None) -> None:
    own_conn = conn is None
    conn = conn or connect()
    now = datetime.now().isoformat(timespec="seconds")
    try:
        conn.executemany(
            """
            INSERT OR IGNORE INTO semantic_dictionary
                (term, definition, aliases, approved, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [(term, definition, aliases, approved, now) for term, definition, aliases, approved in DEFAULT_SEMANTIC_TERMS],
        )
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            conn.close()


def get_param(clave: str, default: str = "") -> str:
    conn = connect()
    try:
        row = conn.execute("SELECT valor FROM app_parametros WHERE clave = ?", (clave,)).fetchone()
        return row["valor"] if row else default
    finally:
        conn.close()


def set_param(clave: str, valor: str, descripcion: str = "") -> None:
    conn = connect()
    try:
        conn.execute(
            """
            INSERT INTO app_parametros (clave, valor, descripcion, actualizado_en)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(clave) DO UPDATE SET
                valor = excluded.valor,
                descripcion = excluded.descripcion,
                actualizado_en = excluded.actualizado_en
            """,
            (clave, valor, descripcion, datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
    finally:
        conn.close()


def upsert_semantic_term(term: str, definition: str, aliases: str = "", approved: bool = True) -> None:
    conn = connect()
    try:
        conn.execute(
            """
            INSERT INTO semantic_dictionary (term, definition, aliases, approved, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(term) DO UPDATE SET
                definition = excluded.definition,
                aliases = excluded.aliases,
                approved = excluded.approved
            """,
            (
                term.strip(),
                definition.strip(),
                aliases.strip(),
                1 if approved else 0,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def add_training_entry(question: str, expected_intent: str, expected_response: str = "", approved: bool = True) -> None:
    conn = connect()
    try:
        conn.execute(
            """
            INSERT INTO training_entries
                (question, expected_intent, expected_response, approved, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                question.strip(),
                expected_intent.strip(),
                expected_response.strip(),
                1 if approved else 0,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def approved_semantic_dictionary() -> pd.DataFrame:
    conn = connect()
    try:
        return pd.read_sql_query(
            """
            SELECT term, definition, aliases
            FROM semantic_dictionary
            WHERE approved = 1
            ORDER BY term
            """,
            conn,
        )
    finally:
        conn.close()


def approved_training_entries() -> pd.DataFrame:
    conn = connect()
    try:
        return pd.read_sql_query(
            """
            SELECT question, expected_intent, expected_response
            FROM training_entries
            WHERE approved = 1
            ORDER BY id DESC
            """,
            conn,
        )
    finally:
        conn.close()


def read_table(table_name: str) -> pd.DataFrame:
    conn = connect()
    try:
        return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    finally:
        conn.close()
