/*
    WallyAgent 4.0
    Script 08 - Consultas manuales para validar reglas en servidor.

    Este script no modifica datos. Usarlo durante la revision funcional contra
    SmartBit antes de cerrar Fase 1.
*/

USE WallyBD;
GO

DECLARE @FechaDesde date = CAST(GETDATE() AS date);
DECLARE @FechaHasta date = CAST(GETDATE() AS date);

SELECT @FechaDesde AS FechaDesde, @FechaHasta AS FechaHasta;
GO

SELECT
    COUNT_BIG(*) AS Documentos,
    SUM(CASE WHEN FlagCambioVendedor = 1 THEN 1 ELSE 0 END) AS CambioVendedor,
    SUM(CASE WHEN FlagCambioPosteriorPago = 1 THEN 1 ELSE 0 END) AS PosteriorPago,
    SUM(CASE WHEN FlagCambioPosteriorCierre = 1 THEN 1 ELSE 0 END) AS PosteriorCierre,
    SUM(CASE WHEN FlagCambioTardio = 1 THEN 1 ELSE 0 END) AS CambioTardio,
    SUM(CASE WHEN FlagPosibleNotaCredito = 1 THEN 1 ELSE 0 END) AS PosibleNotaCredito
FROM dbo.vw_AuditoriaCambioVendedor
WHERE CAST(Fecha AS date) = CAST(GETDATE() AS date);
GO

SELECT TOP (50)
    idSucursal,
    idMovimientoInv,
    Numero,
    Fecha,
    idTransaccionInv,
    TransaccionInvDescripcion,
    idMovimientoInvRef,
    Total,
    VendedorInicial,
    VendedorFinalBIT,
    FlagCambioVendedor,
    FechaUltimoCambio,
    FechaUltimoPago,
    SegundosDespuesPago,
    FlagCambioPosteriorPago,
    FechaUltimoCierre,
    FlagCambioPosteriorCierre,
    DATEDIFF(MINUTE, FechaUltimoCierre, FechaUltimoCambio) AS MinutosDespuesCierre,
    UsuarioUltimoCambio,
    CantidadEventosBIT,
    CantidadCambiosDetectados,
    FlagCambioTardio,
    FlagPosibleNotaCredito
FROM dbo.vw_AuditoriaCambioVendedor
WHERE CAST(Fecha AS date) = CAST(GETDATE() AS date)
ORDER BY
    FlagCambioPosteriorCierre DESC,
    FlagCambioPosteriorPago DESC,
    FlagCambioVendedor DESC,
    FechaUltimoCambio DESC;
GO

SELECT
    cases.IdCasoValidacion,
    cases.CodigoRegla,
    rules.NombreRegla,
    cases.Numero,
    cases.idSucursal,
    cases.idMovimientoInv,
    cases.ResultadoEsperado,
    cases.ResultadoVista,
    CASE
        WHEN cases.ResultadoEsperado IS NULL OR cases.ResultadoVista IS NULL THEN 'pendiente'
        WHEN cases.ResultadoEsperado = cases.ResultadoVista THEN 'ok'
        ELSE 'revisar'
    END AS ResultadoComparacion,
    cases.EstadoValidacion,
    cases.Observacion
FROM Audit.CasoValidacionAuditoria AS cases
INNER JOIN Audit.ReglaAuditoria AS rules
    ON rules.CodigoRegla = cases.CodigoRegla
ORDER BY cases.FechaCreacion DESC;
GO
