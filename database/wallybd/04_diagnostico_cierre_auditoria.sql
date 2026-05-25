/*
    WallyAgent 4.0
    Diagnostico de regla posterior al cierre.

    Ejecutar si CambiosPosteriorCierre parece demasiado alto o demasiado bajo.
    Este script no modifica datos.
*/

USE WallyBD;
GO

DECLARE @Fecha date = (
    SELECT MAX(CAST(Fecha AS date))
    FROM dbo.vw_AuditoriaCambioVendedor
);

SELECT @Fecha AS FechaAnalizada;
GO

SELECT
    CAST(Fecha AS date) AS FechaDocumento,
    idSucursal,
    COUNT_BIG(*) AS Documentos,
    SUM(CASE WHEN FechaUltimoCierre IS NULL THEN 1 ELSE 0 END) AS SinCierreMismoDia,
    SUM(CASE WHEN FlagCambioPosteriorCierre = 1 THEN 1 ELSE 0 END) AS PosteriorCierre,
    MIN(FechaUltimoCierre) AS PrimerCierreDetectado,
    MAX(FechaUltimoCierre) AS UltimoCierreDetectado,
    MIN(FechaUltimoCambio) AS PrimerCambioBIT,
    MAX(FechaUltimoCambio) AS UltimoCambioBIT
FROM dbo.vw_AuditoriaCambioVendedor
WHERE CAST(Fecha AS date) = (
    SELECT MAX(CAST(Fecha AS date))
    FROM dbo.vw_AuditoriaCambioVendedor
)
GROUP BY CAST(Fecha AS date), idSucursal
ORDER BY PosteriorCierre DESC, Documentos DESC;
GO

SELECT TOP (50)
    idSucursal,
    idMovimientoInv,
    Numero,
    Fecha,
    FechaUltimoCambio,
    FechaUltimoCierre,
    DATEDIFF(MINUTE, FechaUltimoCierre, FechaUltimoCambio) AS MinutosDespuesCierre,
    UsuarioUltimoCambio,
    VendedorInicial,
    VendedorFinalBIT,
    Total
FROM dbo.vw_AuditoriaCambioVendedor
WHERE FlagCambioPosteriorCierre = 1
ORDER BY FechaUltimoCambio DESC;
GO
