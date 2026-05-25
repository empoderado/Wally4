/*
    WallyAgent 4.0
    Script 03 - Pruebas rapidas de WallyBD.
*/

USE WallyBD;
GO

SELECT TOP (10) *
FROM dbo.vw_AuditoriaCambioVendedor
ORDER BY FechaUltimoCambio DESC;
GO

SELECT
    COUNT_BIG(*) AS FacturasAuditadas,
    SUM(CASE WHEN FlagCambioVendedor = 1 THEN 1 ELSE 0 END) AS CambiosVendedor,
    SUM(CASE WHEN FlagCambioPosteriorPago = 1 THEN 1 ELSE 0 END) AS CambiosPosteriorPago,
    SUM(CASE WHEN FlagCambioPosteriorCierre = 1 THEN 1 ELSE 0 END) AS CambiosPosteriorCierre,
    SUM(CASE WHEN FlagPosibleNotaCredito = 1 THEN 1 ELSE 0 END) AS PosiblesNotasCredito
FROM dbo.vw_AuditoriaCambioVendedor;
GO

SELECT
    CAST(Fecha AS date) AS FechaDocumento,
    COUNT_BIG(*) AS Documentos,
    SUM(CASE WHEN FechaUltimoCierre IS NULL THEN 1 ELSE 0 END) AS SinCierreMismoDia,
    SUM(CASE WHEN FlagCambioPosteriorCierre = 1 THEN 1 ELSE 0 END) AS CambiosPosteriorCierre,
    SUM(CASE WHEN FlagCambioPosteriorPago = 1 THEN 1 ELSE 0 END) AS CambiosPosteriorPago,
    SUM(CASE WHEN FlagCambioTardio = 1 THEN 1 ELSE 0 END) AS CambiosTardios
FROM dbo.vw_AuditoriaCambioVendedor
GROUP BY CAST(Fecha AS date)
ORDER BY FechaDocumento DESC;
GO

SELECT TOP (25)
    idSucursal,
    Numero,
    Fecha,
    FechaUltimoCambio,
    FechaUltimoCierre,
    FlagCambioPosteriorCierre,
    UsuarioUltimoCambio,
    CantidadEventosBIT,
    MinutosHastaUltimoCambio
FROM dbo.vw_AuditoriaCambioVendedor
WHERE FlagCambioPosteriorCierre = 1
ORDER BY FechaUltimoCambio DESC;
GO
