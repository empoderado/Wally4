/*
    WallyAgent 4.0
    Validacion de contrato WallyBD.

    Este script no modifica datos. Sirve para confirmar que las vistas minimas
    existen y que la vista de auditoria expone las columnas esperadas.
*/

USE WallyBD;
GO

SELECT
    required.ViewName,
    CASE WHEN views.object_id IS NULL THEN 'FALTA' ELSE 'OK' END AS Estado
FROM (
    VALUES
        ('dbo.VwFacturaConImpuesto'),
        ('dbo.VwExistencia'),
        ('dbo.VwEntradasInventario'),
        ('dbo.VwClienteResumenCRM'),
        ('dbo.vw_AuditoriaCambioVendedor')
) AS required(ViewName)
LEFT JOIN sys.views AS views
    ON views.object_id = OBJECT_ID(required.ViewName)
ORDER BY required.ViewName;
GO

SELECT
    required.ColumnName,
    CASE WHEN columns.name IS NULL THEN 'FALTA' ELSE 'OK' END AS Estado
FROM (
    VALUES
        ('idSucursal'),
        ('idMovimientoInv'),
        ('Numero'),
        ('Fecha'),
        ('idUsuario'),
        ('idTransaccionInv'),
        ('TransaccionInvDescripcion'),
        ('idMovimientoInvRef'),
        ('idEmpleadoCajero'),
        ('Total'),
        ('VendedorInicial'),
        ('VendedorFinalBIT'),
        ('FlagCambioVendedor'),
        ('FechaPrimerRegistro'),
        ('UsuarioPrimerRegistro'),
        ('FechaUltimoCambio'),
        ('UsuarioUltimoCambio'),
        ('FechaPrimerPago'),
        ('FechaUltimoPago'),
        ('CantidadPagos'),
        ('SegundosDespuesPago'),
        ('FlagCambioPosteriorPago'),
        ('FechaUltimoCierre'),
        ('FlagCambioPosteriorCierre'),
        ('CantidadEventosBIT'),
        ('CantidadCambiosDetectados'),
        ('MinutosHastaUltimoCambio'),
        ('FlagCambioTardio'),
        ('FlagPosibleNotaCredito'),
        ('TipoAlerta'),
        ('NivelRiesgo'),
        ('EsRiesgoFraude')
) AS required(ColumnName)
LEFT JOIN sys.columns AS columns
    ON columns.object_id = OBJECT_ID('dbo.vw_AuditoriaCambioVendedor')
   AND columns.name = required.ColumnName
ORDER BY required.ColumnName;
GO

SELECT
    COUNT_BIG(*) AS Documentos,
    SUM(CASE WHEN FlagCambioVendedor = 1 THEN 1 ELSE 0 END) AS CambiosVendedor,
    SUM(CASE WHEN FlagCambioPosteriorPago = 1 THEN 1 ELSE 0 END) AS CambiosPosteriorPago,
    SUM(CASE WHEN FlagCambioPosteriorCierre = 1 THEN 1 ELSE 0 END) AS CambiosPosteriorCierre,
    SUM(CASE WHEN FlagPosibleNotaCredito = 1 THEN 1 ELSE 0 END) AS PosiblesNotasCredito,
    SUM(CASE WHEN EsRiesgoFraude = 1 THEN 1 ELSE 0 END) AS RiesgoFraude,
    MIN(Fecha) AS MinFecha,
    MAX(Fecha) AS MaxFecha
FROM dbo.vw_AuditoriaCambioVendedor;
GO
