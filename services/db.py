from __future__ import annotations

import warnings
import re
from collections import OrderedDict
from datetime import date, timedelta
from threading import RLock
from time import monotonic

import pandas as pd

from services.paths import APP_DIR
from services.env import env_value, load_app_env

try:
    import pyodbc
except ImportError:  # pragma: no cover
    pyodbc = None


warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")

VIEW_VENTAS = "dbo.VwFacturaConImpuesto"
VIEW_EXISTENCIA = "dbo.VwExistencia"
VIEW_ENTRADAS = "dbo.VwEntradasInventario"
VIEW_CRM = "dbo.VwClienteResumenCRM"
VIEW_AUDITORIA_CAMBIO_VENDEDOR = "dbo.vw_AuditoriaCambioVendedor"
VIEW_COLABORADORES_TURNO = "dbo.VwColaboradoresTurno"
AUTHORIZED_VIEWS = {VIEW_VENTAS, VIEW_EXISTENCIA, VIEW_ENTRADAS, VIEW_CRM, VIEW_AUDITORIA_CAMBIO_VENDEDOR, VIEW_COLABORADORES_TURNO}
VIEW_BRANCH_COLUMNS = {
    VIEW_VENTAS: "Sucursal",
    VIEW_EXISTENCIA: "Sucursal",
    VIEW_ENTRADAS: "Sucursal",
    VIEW_CRM: "SucursalPreferida",
    VIEW_AUDITORIA_CAMBIO_VENDEDOR: "Sucursal",
}
REQUIRED_SQL_DATABASE = "WallyBD"
QUERY_CACHE_TTL_SECONDS = 600
QUERY_CACHE_MAX_ENTRIES = 64
_QUERY_CACHE: OrderedDict[tuple[str, tuple], tuple[float, pd.DataFrame]] = OrderedDict()
_QUERY_CACHE_LOCK = RLock()


def load_environment() -> None:
    load_app_env()


def use_mock_data() -> bool:
    load_environment()
    if app_environment() == "production":
        return False
    return mock_data_requested()


def mock_data_requested() -> bool:
    load_environment()
    return env_value("USE_MOCK_DATA", "no").lower() in {"yes", "si", "true", "1"}


def data_source_label() -> str:
    return "Datos simulados" if use_mock_data() else "SQL Server real"


def app_environment() -> str:
    load_environment()
    return env_value("APP_ENV", "production").lower() or "production"


def connection_string() -> str:
    load_environment()
    driver = resolve_sql_driver(env_value("SQL_DRIVER", "ODBC Driver 17 for SQL Server"))
    server = env_value("SQL_SERVER")
    database = env_value("SQL_DATABASE")
    username = env_value("SQL_USERNAME")
    password = env_value("SQL_PASSWORD")
    trusted = env_value("SQL_TRUSTED_CONNECTION", "yes").lower() in {"yes", "true", "1", "si"}
    if not server or not database:
        raise RuntimeError(f"Configure SQL_SERVER y SQL_DATABASE en {APP_DIR / '.env'}")
    if app_environment() == "production" and database.lower() != REQUIRED_SQL_DATABASE.lower():
        raise RuntimeError(f"Wally4 solo puede conectarse a {REQUIRED_SQL_DATABASE}. SQL_DATABASE actual: {database}")
    parts = [f"DRIVER={{{driver}}}", f"SERVER={server}", f"DATABASE={database}", "TrustServerCertificate=yes"]
    if trusted:
        parts.append("Trusted_Connection=yes")
    else:
        parts.extend([f"UID={username}", f"PWD={password}"])
    return ";".join(parts)


def resolve_sql_driver(preferred_driver: str) -> str:
    if pyodbc is None:
        return preferred_driver
    installed = set(pyodbc.drivers())
    if preferred_driver in installed:
        return preferred_driver
    for candidate in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "SQL Server"):
        if candidate in installed:
            return candidate
    return preferred_driver


def get_connection():
    if pyodbc is None:
        raise RuntimeError("Falta instalar pyodbc. Ejecute pip install -r requirements.txt.")
    return pyodbc.connect(connection_string(), timeout=30)


def _query_cache_key(query: str, params: tuple) -> tuple[str, tuple]:
    normalized_params = tuple((type(value).__qualname__, repr(value)) for value in params)
    return query, normalized_params


def _read_sql_uncached(query: str, params: tuple) -> pd.DataFrame:
    if use_mock_data():
        return mock_read_sql(query, params=params)
    conn = get_connection()
    try:
        return pd.read_sql(query, conn, params=params)
    finally:
        conn.close()


def _apply_branch_scope(query: str) -> str:
    from services.branches import sql_excluded_branch_values

    excluded_values = sql_excluded_branch_values()
    if not excluded_values:
        return query
    literals = sql_literal_list(excluded_values)
    scope_names = {
        VIEW_VENTAS: "WallyScopeVentas",
        VIEW_EXISTENCIA: "WallyScopeExistencia",
        VIEW_ENTRADAS: "WallyScopeEntradas",
        VIEW_CRM: "WallyScopeCRM",
        VIEW_AUDITORIA_CAMBIO_VENDEDOR: "WallyScopeAuditoria",
    }
    scoped = query
    ctes = []
    for view_name, column_name in VIEW_BRANCH_COLUMNS.items():
        if view_name.lower() not in query.lower():
            continue
        scope_name = scope_names[view_name]
        condition = (
            f"UPPER(LTRIM(RTRIM(CAST({column_name} AS varchar(250))))) "
            f"NOT IN ({literals})"
        )
        ctes.append(f"{scope_name} AS (SELECT * FROM {view_name} WHERE {condition})")
        scoped = re.sub(re.escape(view_name), scope_name, scoped, flags=re.IGNORECASE)
    if not ctes:
        return query
    stripped = scoped.lstrip()
    leading = scoped[: len(scoped) - len(stripped)]
    if stripped.lower().startswith("with "):
        return f"{leading}WITH {', '.join(ctes)}, {stripped[5:]}"
    return f"{leading}WITH {', '.join(ctes)} {stripped}"


def read_sql(query: str, params: tuple | list | None = None, apply_branch_filter: bool = True) -> pd.DataFrame:
    if not is_safe_select(query):
        raise PermissionError("Por favor por seguridad primero discuteelo con el administrador.")
    effective_query = _apply_branch_scope(query) if apply_branch_filter else query
    normalized_params = tuple(params or ())
    cache_key = _query_cache_key(effective_query, normalized_params)
    now = monotonic()
    with _QUERY_CACHE_LOCK:
        cached = _QUERY_CACHE.get(cache_key)
        if cached and cached[0] > now:
            _QUERY_CACHE.move_to_end(cache_key)
            return cached[1].copy(deep=True)
        if cached:
            _QUERY_CACHE.pop(cache_key, None)

    result = _read_sql_uncached(effective_query, normalized_params)
    with _QUERY_CACHE_LOCK:
        expired_keys = [key for key, (expires_at, _) in _QUERY_CACHE.items() if expires_at <= now]
        for key in expired_keys:
            _QUERY_CACHE.pop(key, None)
        _QUERY_CACHE[cache_key] = (monotonic() + QUERY_CACHE_TTL_SECONDS, result.copy(deep=True))
        _QUERY_CACHE.move_to_end(cache_key)
        while len(_QUERY_CACHE) > QUERY_CACHE_MAX_ENTRIES:
            _QUERY_CACHE.popitem(last=False)
    return result


def clear_query_cache() -> None:
    with _QUERY_CACHE_LOCK:
        _QUERY_CACHE.clear()


def save_colaborador_turno(id_empleado: int, turno: str) -> None:
    if use_mock_data():
        return
    query = """
        MERGE dbo.ColaboradorTurno AS target
        USING (SELECT ? AS idEmpleado, ? AS Turno) AS source
        ON (target.idEmpleado = source.idEmpleado)
        WHEN MATCHED THEN
            UPDATE SET target.Turno = source.Turno, target.FechaActualizado = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (idEmpleado, Turno, FechaActualizado)
            VALUES (source.idEmpleado, source.Turno, GETDATE());
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, (id_empleado, turno))
        conn.commit()
    finally:
        conn.close()
    clear_query_cache()


def is_safe_select(query: str) -> bool:
    normalized = " ".join(query.strip().lower().split())
    forbidden = [" insert ", " update ", " delete ", " drop ", " alter ", " exec ", " execute ", " merge ", " truncate "]
    if not normalized.startswith("select") and not normalized.startswith("with"):
        return False
    padded = f" {normalized} "
    if any(token in padded for token in forbidden):
        return False
    if references_blocked_database_or_object(normalized):
        return False
    return uses_only_authorized_views(normalized)


def uses_only_authorized_views(normalized_query: str) -> bool:
    if is_allowed_system_query(normalized_query):
        return True
    referenced_views = {
        view.lower()
        for view in AUTHORIZED_VIEWS
        if view.lower() in normalized_query
    }
    allowed_extra = {"studiof.dbo.promocion", "studiof.dbo.promocionarticuloaplica"}
    if not referenced_views and not any(tbl in normalized_query for tbl in allowed_extra):
        return False

    cte_names = extract_cte_names(normalized_query)
    source_objects = extract_source_objects(normalized_query)
    if not source_objects:
        return True
    for source in source_objects:
        normalized_source = normalize_sql_identifier(source)
        if normalized_source in cte_names:
            continue
        if normalized_source in allowed_extra:
            continue
        if normalized_source not in referenced_views:
            return False
    return True


def is_allowed_system_query(normalized_query: str) -> bool:
    return normalized_query in {
        "select db_name() as basedatos, @@servername as servidor",
        "select @@servername as servidor, db_name() as basedatos",
    }


def references_blocked_database_or_object(normalized_query: str) -> bool:
    clean_q = normalized_query.replace("studiof.dbo.promocionarticuloaplica", "").replace("studiof.dbo.promocion", "")
    if "studiof." in clean_q:
        return True
    if re.search(r"\b[a-z_][\w]*\.[a-z_][\w]*\.[a-z_][\w]*\b", clean_q):
        return True
    return False


def extract_cte_names(normalized_query: str) -> set[str]:
    if not normalized_query.startswith("with "):
        return set()
    return {
        normalize_sql_identifier(match.group(1))
        for match in re.finditer(r"(?:with|,)\s+([a-z_][\w]*)\s+as\s*\(", normalized_query)
    }


def extract_source_objects(normalized_query: str) -> list[str]:
    sources: list[str] = []
    pattern = re.compile(r"\b(?:from|join|apply)\s+([a-z_][\w]*(?:\.[a-z_][\w]*){0,2}|\[[^\]]+\](?:\.\[[^\]]+\]){0,2})")
    for match in pattern.finditer(normalized_query):
        sources.append(match.group(1))
    return sources


def normalize_sql_identifier(identifier: str) -> str:
    return identifier.replace("[", "").replace("]", "").lower()


def test_connection() -> tuple[bool, str]:
    if use_mock_data():
        return True, "Modo desarrollo activo: usando datos simulados, sin conexion a SQL Server."
    try:
        df = read_sql("SELECT DB_NAME() AS BaseDatos, @@SERVERNAME AS Servidor")
        row = df.iloc[0]
        return True, f"Conexion correcta: {row['Servidor']} / {row['BaseDatos']}"
    except Exception as exc:
        return False, str(exc)


def min_max_date() -> tuple[date, date]:
    df = read_sql(f"SELECT MIN(CAST(Fecha AS date)) AS MinFecha, MAX(CAST(Fecha AS date)) AS MaxFecha FROM {VIEW_VENTAS}")
    today = date.today()
    if df.empty or pd.isna(df.iloc[0]["MaxFecha"]):
        return today, today
    return pd.to_datetime(df.iloc[0]["MinFecha"]).date(), pd.to_datetime(df.iloc[0]["MaxFecha"]).date()


def default_sales_date() -> date:
    today = date.today()
    if use_mock_data():
        return today
    try:
        df = read_sql(
            f"""
            SELECT
                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM {VIEW_VENTAS}
                        WHERE CAST(Fecha AS date) = CAST(GETDATE() AS date)
                    )
                    THEN CAST(GETDATE() AS date)
                    ELSE (
                        SELECT MAX(CAST(Fecha AS date))
                        FROM {VIEW_VENTAS}
                        WHERE CAST(Fecha AS date) < CAST(GETDATE() AS date)
                    )
                END AS FechaDefault
            """
        )
        if not df.empty and not pd.isna(df.iloc[0]["FechaDefault"]):
            return pd.to_datetime(df.iloc[0]["FechaDefault"]).date()
    except Exception:
        pass
    return today - timedelta(days=1)


def distinct_values(view_name: str, column_name: str, where: str = "1=1") -> list[str]:
    query = f"""
        SELECT DISTINCT {column_name} AS Valor
        FROM {view_name}
        WHERE {where}
          AND {column_name} IS NOT NULL
          AND LTRIM(RTRIM(CAST({column_name} AS varchar(250)))) <> ''
        ORDER BY {column_name}
    """
    df = read_sql(query)
    return [str(v) for v in df["Valor"].dropna().tolist()]


def sql_literal_list(values: list[str]) -> str:
    safe = [str(v).replace("'", "''") for v in values if str(v).strip()]
    return ", ".join(f"'{v}'" for v in safe)


def date_params(start_date: date, end_date: date) -> tuple[str, str]:
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def mock_read_sql(query: str, params: tuple | list | None = None) -> pd.DataFrame:
    normalized = " ".join(query.lower().split())
    params = list(params or [])
    today = date.today().isoformat()
    if "@@servername" in normalized or "db_name()" in normalized:
        return pd.DataFrame([{"BaseDatos": "WallyBD Mock", "Servidor": "Modo desarrollo"}])
    if "min(cast(fecha as date))" in normalized and "max(cast(fecha as date))" in normalized:
        return pd.DataFrame([{"MinFecha": date(2023, 1, 1), "MaxFecha": date.today()}])
    if "select distinct" in normalized and " as valor" in normalized:
        if "sucursal" in normalized:
            return pd.DataFrame({"Valor": ["OAKLAND", "PRADERA", "CHIQUIMULA", "MAJADAS", "NARANJO MALL"]})
        if "linea" in normalized:
            return pd.DataFrame({"Valor": ["JEAN", "BLUSA", "BODY"]})
        if "descriptioprenda" in normalized or "descriptipop" in normalized:
            return pd.DataFrame({"Valor": ["JEAN", "BLUSA", "BODY"]})
        if "vendedor" in normalized:
            return pd.DataFrame({"Valor": ["MARIA VALLE", "ASHLEY GOMEZ", "EMILIN OADILLA"]})
        return pd.DataFrame({"Valor": []})
    if "from dbo.vw_auditoriacambiovendedor" in normalized:
        audit_rows = pd.DataFrame(
            [
                {
                    "idSucursal": 1,
                    "idMovimientoInv": 10001,
                    "Numero": "FV-10001",
                    "Fecha": today,
                    "idUsuario": 12,
                    "idEmpleadoCajero": 501,
                    "Total": 2450.0,
                    "VendedorInicial": 501,
                    "VendedorFinalBIT": 518,
                    "FlagCambioVendedor": 1,
                    "FechaPrimerRegistro": today,
                    "UsuarioPrimerRegistro": "caja01",
                    "FechaUltimoCambio": today,
                    "UsuarioUltimoCambio": "supervisor01",
                    "FechaPrimerPago": today,
                    "FechaUltimoPago": today,
                    "CantidadPagos": 1,
                    "FlagCambioPosteriorPago": 1,
                    "FechaUltimoCierre": today,
                    "FlagCambioPosteriorCierre": 0,
                    "CantidadEventosBIT": 3,
                    "CantidadCambiosDetectados": 2,
                    "MinutosHastaUltimoCambio": 84,
                    "FlagCambioTardio": 1,
                    "FlagPosibleNotaCredito": 0,
                },
                {
                    "idSucursal": 2,
                    "idMovimientoInv": 10002,
                    "Numero": "NC-10002",
                    "Fecha": today,
                    "idUsuario": 15,
                    "idEmpleadoCajero": 602,
                    "Total": -475.0,
                    "VendedorInicial": 602,
                    "VendedorFinalBIT": 602,
                    "FlagCambioVendedor": 0,
                    "FechaPrimerRegistro": today,
                    "UsuarioPrimerRegistro": "caja02",
                    "FechaUltimoCambio": today,
                    "UsuarioUltimoCambio": "caja02",
                    "FechaPrimerPago": today,
                    "FechaUltimoPago": today,
                    "CantidadPagos": 1,
                    "FlagCambioPosteriorPago": 0,
                    "FechaUltimoCierre": today,
                    "FlagCambioPosteriorCierre": 1,
                    "CantidadEventosBIT": 2,
                    "CantidadCambiosDetectados": 1,
                    "MinutosHastaUltimoCambio": 25,
                    "FlagCambioTardio": 0,
                    "FlagPosibleNotaCredito": 1,
                },
            ]
        )
        if "group by usuarioultimocambio" in normalized:
            return pd.DataFrame(
                [
                    {
                        "UsuarioUltimoCambio": "supervisor01",
                        "Documentos": 1,
                        "CambiosVendedor": 1,
                        "CambiosPosteriorPago": 1,
                        "CambiosPosteriorCierre": 0,
                        "MontoAuditado": 2450.0,
                    },
                    {
                        "UsuarioUltimoCambio": "caja02",
                        "Documentos": 1,
                        "CambiosVendedor": 0,
                        "CambiosPosteriorPago": 0,
                        "CambiosPosteriorCierre": 1,
                        "MontoAuditado": -475.0,
                    },
                ]
            )
        if "count_big(*) as documentos" in normalized and "group by" not in normalized:
            return pd.DataFrame(
                [
                    {
                        "Documentos": 2,
                        "CambiosVendedor": 1,
                        "CambiosPosteriorPago": 1,
                        "CambiosPosteriorCierre": 1,
                        "CambiosTardios": 1,
                        "PosiblesNotasCredito": 1,
                        "MontoAuditado": 1975.0,
                    }
                ]
            )
        return audit_rows
    if "from dbo.vwfacturaconimpuesto" in normalized and "group by sucursal, cast(idvendedor as varchar(50)), vendedor" in normalized:
        return _filter_mock_by_params(
            pd.DataFrame(
                [
                    {"Sucursal": "OAKLAND", "IdVendedor": "101", "Asesor": "MARIA VALLE", "Unidades": 39, "VentaQ": 24014.0, "Facturas": 21, "MargenQ": 14200.0},
                    {"Sucursal": "OAKLAND", "IdVendedor": "102", "Asesor": "ASHLEY GOMEZ", "Unidades": 38, "VentaQ": 23124.0, "Facturas": 19, "MargenQ": 13650.0},
                    {"Sucursal": "PRADERA", "IdVendedor": "103", "Asesor": "EMILIN OADILLA", "Unidades": 24, "VentaQ": 12304.0, "Facturas": 21, "MargenQ": 7300.0},
                    {"Sucursal": "PRADERA", "IdVendedor": "104", "Asesor": "KAREN LOPEZ", "Unidades": 25, "VentaQ": 15678.0, "Facturas": 19, "MargenQ": 8900.0},
                ]
            ),
            params,
        )
    if "from dbo.vwfacturaconimpuesto" in normalized and "group by sucursal" in normalized:
        return _filter_mock_by_params(
            pd.DataFrame(
            [
                _sales_mock_row("Sucursal", "OAKLAND", 38250.0, 61, 25, 22850.0),
                _sales_mock_row("Sucursal", "PRADERA", 27450.0, 48, 21, 16250.0),
                _sales_mock_row("Sucursal", "CHIQUIMULA", 21100.0, 37, 18, 12500.0),
                _sales_mock_row("Sucursal", "MAJADAS", 18500.0, 30, 14, 11000.0),
                _sales_mock_row("Sucursal", "NARANJO MALL", 13200.0, 22, 10, 7750.0),
            ]
            ),
            params,
        )
    if "from dbo.vwfacturaconimpuesto" in normalized and "group by vendedor" in normalized:
        return pd.DataFrame(
            [
                _sales_mock_row("Vendedor", "MARIA VALLE", 24780.0, 40, 18, 14500.0),
                _sales_mock_row("Vendedor", "ASHLEY GOMEZ", 21350.0, 35, 16, 12400.0),
                _sales_mock_row("Vendedor", "EMILIN OADILLA", 16890.0, 27, 12, 9800.0),
            ]
        )
    if "from dbo.vwfacturaconimpuesto" in normalized and "group by codembarqueabreviado" in normalized:
        return pd.DataFrame(
            [
                _sales_mock_row("CodEmbarqueAbreviado", "E13-26", 31000.0, 52, 22, 18100.0),
                _sales_mock_row("CodEmbarqueAbreviado", "E11-26", 28750.0, 45, 20, 16700.0),
                _sales_mock_row("CodEmbarqueAbreviado", "E9-26", 19800.0, 31, 14, 11200.0),
            ]
        )
    if "from dbo.vwfacturaconimpuesto" in normalized and "group by linea" in normalized:
        return pd.DataFrame(
            [
                _sales_mock_row("Linea", "JEAN", 45100.0, 70, 32, 26800.0),
                _sales_mock_row("Linea", "BLUSA", 30300.0, 58, 27, 17700.0),
                _sales_mock_row("Linea", "BODY", 18100.0, 25, 12, 10200.0),
            ]
        )
    if "from dbo.vwfacturaconimpuesto" in normalized and "group by referencia" in normalized:
        return pd.DataFrame(
            [
                _sales_mock_row("Referencia", "S506345", 22400.0, 38, 18, 13200.0),
                _sales_mock_row("Referencia", "DFS740180A", 18100.0, 29, 14, 10400.0),
                _sales_mock_row("Referencia", "S163469", 14300.0, 22, 11, 8600.0),
            ]
        )
    if "from dbo.vwfacturaconimpuesto" in normalized and "group by descriptipoprenda" in normalized:
        return pd.DataFrame(
            [
                _sales_mock_row("DescripTipoPrenda", "JEAN", 38200.0, 61, 28, 22400.0),
                _sales_mock_row("DescripTipoPrenda", "BLUSA", 29100.0, 50, 24, 17000.0),
                _sales_mock_row("DescripTipoPrenda", "BODY", 17200.0, 27, 13, 9800.0),
            ]
        )
    if "from dbo.vwfacturaconimpuesto" in normalized and "group by color" in normalized:
        return pd.DataFrame(
            [
                _sales_mock_row("Color", "NEGRO", 21400.0, 36, 17, 12500.0),
                _sales_mock_row("Color", "NAVY", 18800.0, 29, 14, 11000.0),
                _sales_mock_row("Color", "BLANCO", 12100.0, 20, 10, 6900.0),
            ]
        )
    if "from dbo.vwfacturaconimpuesto" in normalized and "group by talla" in normalized:
        return pd.DataFrame(
            [
                _sales_mock_row("Talla", "S", 18200.0, 31, 15, 10600.0),
                _sales_mock_row("Talla", "M", 16400.0, 28, 13, 9700.0),
                _sales_mock_row("Talla", "L", 10800.0, 18, 9, 6100.0),
            ]
        )
    if "from dbo.vwfacturaconimpuesto" in normalized and "group by cuenta, cliente" in normalized:
        rows = [
            {"Cuenta": "1234567", "Cliente": "CLIENTE VIP OAKLAND", "VentaNetaQ": 18500.0, "Unidades": 29, "Facturas": 6, "UltimaCompra": today},
            {"Cuenta": "7654321", "Cliente": "CLIENTE PREMIUM PRADERA", "VentaNetaQ": 14200.0, "Unidades": 21, "Facturas": 8, "UltimaCompra": today},
            {"Cuenta": "4567890", "Cliente": "CLIENTE FRECUENTE MAJADAS", "VentaNetaQ": 9900.0, "Unidades": 14, "Facturas": 10, "UltimaCompra": today},
            {"Cuenta": "1122334", "Cliente": "CLIENTE RECURRENTE CHIQUIMULA", "VentaNetaQ": 7600.0, "Unidades": 11, "Facturas": 7, "UltimaCompra": today},
            {"Cuenta": "9988776", "Cliente": "CLIENTE ONLINE", "VentaNetaQ": 6200.0, "Unidades": 9, "Facturas": 5, "UltimaCompra": today},
        ]
        if "order by facturas desc" in normalized:
            rows = sorted(rows, key=lambda row: (row["Facturas"], row["VentaNetaQ"]), reverse=True)
        else:
            rows = sorted(rows, key=lambda row: row["VentaNetaQ"], reverse=True)
        return pd.DataFrame(
            rows
        )
    if "from dbo.vwfacturaconimpuesto" in normalized and "group by cliente" in normalized:
        return pd.DataFrame(
            [
                _sales_mock_row("Cliente", "CLIENTE VIP OAKLAND", 18500.0, 29, 6, 10900.0),
                _sales_mock_row("Cliente", "CLIENTE PREMIUM PRADERA", 14200.0, 21, 8, 8200.0),
                _sales_mock_row("Cliente", "CLIENTE FRECUENTE MAJADAS", 9900.0, 14, 10, 5700.0),
            ]
        )
    if "from dbo.vwfacturaconimpuesto" in normalized and "group by year" in normalized:
        return pd.DataFrame(
            [
                {"Anio": 2023, "VentaNetaQ": 7520000.0, "Unidades": 13250, "Facturas": 6100},
                {"Anio": 2024, "VentaNetaQ": 8210000.0, "Unidades": 14800, "Facturas": 6740},
                {"Anio": 2025, "VentaNetaQ": 9180000.0, "Unidades": 16320, "Facturas": 7350},
                {"Anio": 2026, "VentaNetaQ": 3975000.0, "Unidades": 7020, "Facturas": 3180},
            ]
        )
    if "sum(isnull(ventanetaq" in normalized and "from dbo.vwfacturaconimpuesto" in normalized:
        return pd.DataFrame(
            [
                {
                    "VentaNetaQ": 128450.0,
                    "Unidades": 214,
                    "Facturas": 96,
                    "VentaBruta": 143200.0,
                    "DescuentoQ": 14750.0,
                    "CostoTotal": 51200.0,
                    "MargenQ": 77250.0,
                    "Fecha": today,
                }
            ]
        )
    if "from dbo.vwexistencia" in normalized and "group by codembarqueabreviado" in normalized:
        return pd.DataFrame(
            [
                {"CodEmbarqueAbreviado": "E13-26", "Existencia": 729, "TVida": 8},
                {"CodEmbarqueAbreviado": "E10-26", "Existencia": 697, "TVida": 21},
                {"CodEmbarqueAbreviado": "E9-26", "Existencia": 622, "TVida": 28},
            ]
        )
    if "from dbo.vwexistencia" in normalized and "group by referencia, color" in normalized:
        return pd.DataFrame(
            [
                {"Referencia": "S506345", "Color": "NAVY", "ExistenciaFisica": 5, "ExistenciaDisponible": 5, "TVida": 98},
                {"Referencia": "S506345", "Color": "NEGRO", "ExistenciaFisica": 3, "ExistenciaDisponible": 2, "TVida": 98},
            ]
        )
    if "from dbo.vwexistencia" in normalized and "group by color" in normalized:
        return pd.DataFrame(
            [
                {"Color": "NAVY", "ExistenciaFisica": 120, "ExistenciaDisponible": 112, "TVida": 45},
                {"Color": "NEGRO", "ExistenciaFisica": 95, "ExistenciaDisponible": 90, "TVida": 38},
                {"Color": "BLANCO", "ExistenciaFisica": 64, "ExistenciaDisponible": 60, "TVida": 52},
            ]
        )
    if "from dbo.vwexistencia" in normalized and "group by talla" in normalized:
        return pd.DataFrame(
            [
                {"Talla": "S", "ExistenciaFisica": 140, "ExistenciaDisponible": 132, "TVida": 45},
                {"Talla": "M", "ExistenciaFisica": 118, "ExistenciaDisponible": 110, "TVida": 45},
                {"Talla": "L", "ExistenciaFisica": 80, "ExistenciaDisponible": 75, "TVida": 45},
            ]
        )
    if "from dbo.vwexistencia" in normalized and "group by linea" in normalized:
        return pd.DataFrame(
            [
                {"Linea": "JEAN", "ExistenciaFisica": 2600, "ExistenciaDisponible": 2480, "TVida": 22},
                {"Linea": "BLUSA", "ExistenciaFisica": 2100, "ExistenciaDisponible": 1990, "TVida": 31},
                {"Linea": "BODY", "ExistenciaFisica": 820, "ExistenciaDisponible": 790, "TVida": 18},
            ]
        )
    if "from dbo.vwexistencia" in normalized and "referencia" in normalized and "where" in normalized:
        return pd.DataFrame(
            [
                {"Sucursal": "PRADERA", "Referencia": "S506345", "Talla": "XS", "Color": "NAVY", "CodEmbarqueAbreviado": "E2-26", "ExistenciaFisica": 2, "ExistenciaDisponible": 2, "TVida": 98},
                {"Sucursal": "PRADERA", "Referencia": "S506345", "Talla": "S", "Color": "NAVY", "CodEmbarqueAbreviado": "E2-26", "ExistenciaFisica": 3, "ExistenciaDisponible": 3, "TVida": 98},
            ]
        )
    if "from dbo.vwexistencia" in normalized:
        return pd.DataFrame(
            [
                {"Sucursal": "OAKLAND", "Existencia": 2992},
                {"Sucursal": "CHIQUIMULA", "Existencia": 1998},
                {"Sucursal": "PRADERA", "Existencia": 2104},
            ]
        )
    if "from dbo.vwcolaboradoresturno" in normalized:
        return pd.DataFrame(
            [
                {
                    "CODIGO": 7,
                    "Documento": "2171073770101",
                    "Fecha Creacion": "2024-01-15 08:30:00",
                    "Nombre": "Maria Lourdes Hernandez",
                    "Cargo": "Vendedor",
                    "Sucursal": "OAKLAND",
                    "Turno": "Diurno",
                    "Fecha de alta": "2024-02-01 10:00:00",
                    "Activo": True,
                },
                {
                    "CODIGO": 15,
                    "Documento": "3464862540101",
                    "Fecha Creacion": "2024-01-20 09:15:00",
                    "Nombre": "Rosana Patricia Tercero Garcia",
                    "Cargo": "Cajero",
                    "Sucursal": "PRADERA",
                    "Turno": "Mixto",
                    "Fecha de alta": "2024-02-05 11:30:00",
                    "Activo": True,
                },
                {
                    "CODIGO": 19,
                    "Documento": "3629106500101",
                    "Fecha Creacion": "2024-01-22 14:00:00",
                    "Nombre": "ELIZABETH CU RAMIREZ",
                    "Cargo": "Bodeguero",
                    "Sucursal": "PORTAL PETAPA",
                    "Turno": "Nocturno",
                    "Fecha de alta": None,
                    "Activo": False,
                },
            ]
        )
    return pd.DataFrame()


def _sales_mock_row(dimension: str, value: str, venta: float, unidades: int, facturas: int, margen: float) -> dict:
    return {
        dimension: value,
        "Venta": venta,
        "VentaNetaQ": venta,
        "Unidades": unidades,
        "Facturas": facturas,
        "Margen": margen,
        "MargenQ": margen,
        "TicketPromedio": venta / facturas if facturas else 0,
        "UPT": unidades / facturas if facturas else 0,
        "VrUnidadPromedio": venta / unidades if unidades else 0,
        "PorcMargen": margen / (venta / 1.12) if venta else 0,
    }


def _filter_mock_by_params(df: pd.DataFrame, params: list) -> pd.DataFrame:
    if df.empty or "Sucursal" not in df.columns:
        return df
    branches = {str(param).upper() for param in params if isinstance(param, str)}
    known = {"OAKLAND", "PRADERA", "CHIQUIMULA", "MAJADAS", "NARANJO MALL", "AMERICAS", "ON-LINE", "BASSHERT", "ESCUINTLA"}
    selected = branches & known
    if not selected:
        return df
    return df[df["Sucursal"].str.upper().isin(selected)].reset_index(drop=True)
