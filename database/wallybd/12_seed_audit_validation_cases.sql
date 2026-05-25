/*
    WallyAgent 4.0
    Script 12 - Casos reales de validacion funcional de auditoria.

    Registra evidencia revisada contra datos reales. No modifica StudioF.
*/

USE WallyBD;
GO

DECLARE @Ahora datetime2(0) = SYSDATETIME();

WITH Casos AS (
    SELECT
        source.CodigoRegla,
        source.idSucursal,
        source.idMovimientoInv,
        source.Numero,
        source.ResultadoEsperado,
        source.ResultadoVista,
        source.EstadoValidacion,
        source.Observacion
    FROM (
        VALUES
            (
                'AUD-CAMBIO-TARDIO',
                8,
                CONVERT(bigint, 111600000),
                'S008T001592',
                CONVERT(bit, 0),
                CONVERT(bit, 0),
                'ok',
                'Transferencia operativa Exporta a Sucursal idTransaccionInv=4; sin cambio de vendedor; debe quedar fuera de cambio tardio.'
            ),
            (
                'AUD-CAMBIO-TARDIO',
                11,
                CONVERT(bigint, 111608000),
                'S011T001168',
                CONVERT(bit, 0),
                CONVERT(bit, 0),
                'ok',
                'Transferencia operativa Exporta a Sucursal idTransaccionInv=4; sin cambio de vendedor; debe quedar fuera de cambio tardio.'
            ),
            (
                'AUD-NOTA-CREDITO',
                10,
                CONVERT(bigint, 111616000),
                'S008T001592',
                CONVERT(bit, 0),
                CONVERT(bit, 0),
                'ok',
                'Importa de Sucursal idTransaccionInv=5 con idMovimientoInvRef; no debe clasificarse como nota credito.'
            ),
            (
                'AUD-NOTA-CREDITO',
                10,
                CONVERT(bigint, 111617000),
                'S011T001168',
                CONVERT(bit, 0),
                CONVERT(bit, 0),
                'ok',
                'Importa de Sucursal idTransaccionInv=5 con idMovimientoInvRef; no debe clasificarse como nota credito.'
            ),
            (
                'AUD-NOTA-CREDITO',
                2,
                CONVERT(bigint, 111618000),
                'NCOAK2 00000087',
                CONVERT(bit, 1),
                CONVERT(bit, 1),
                'ok',
                'Nota de credito cliente idTransaccionInv=10; debe clasificarse como nota credito.'
            ),
            (
                'AUD-CAMBIO-VENDEDOR',
                4,
                CONVERT(bigint, 43837000),
                '205',
                CONVERT(bit, 0),
                CONVERT(bit, 0),
                'ok',
                'Pedido historico idTransaccionInv=31 con VendedorInicial 7 y VendedorFinalBIT 74. Negocio confirmo que Pedido no debe auditarse como cambio de vendedor.'
            ),
            (
                'AUD-POST-CIERRE',
                11,
                CONVERT(bigint, 111608000),
                'S011T001168',
                CONVERT(bit, 0),
                CONVERT(bit, 0),
                'ok',
                'Transferencia operativa idTransaccionInv=5/4 posterior al cierre; negocio la clasifica como operativa y queda fuera de AUD-POST-CIERRE.'
            )
    ) AS source(CodigoRegla, idSucursal, idMovimientoInv, Numero, ResultadoEsperado, ResultadoVista, EstadoValidacion, Observacion)
)
INSERT INTO Audit.CasoValidacionAuditoria (
    CodigoRegla,
    idSucursal,
    idMovimientoInv,
    Numero,
    ResultadoEsperado,
    ResultadoVista,
    EstadoValidacion,
    Observacion,
    ValidadoPor,
    FechaValidacion
)
SELECT
    casos.CodigoRegla,
    casos.idSucursal,
    casos.idMovimientoInv,
    casos.Numero,
    casos.ResultadoEsperado,
    casos.ResultadoVista,
    casos.EstadoValidacion,
    casos.Observacion,
    SUSER_SNAME(),
    @Ahora
FROM Casos AS casos
WHERE NOT EXISTS (
    SELECT 1
    FROM Audit.CasoValidacionAuditoria AS existing
    WHERE existing.CodigoRegla = casos.CodigoRegla
      AND existing.idSucursal = casos.idSucursal
      AND existing.idMovimientoInv = casos.idMovimientoInv
);
GO

UPDATE rules
SET Estado =
        CASE
            WHEN rules.CodigoRegla IN ('AUD-CAMBIO-TARDIO', 'AUD-NOTA-CREDITO') THEN 'validacion_tecnica_ok'
            WHEN rules.CodigoRegla IN ('AUD-CAMBIO-VENDEDOR', 'AUD-POST-CIERRE') THEN 'validacion_funcional_ok'
            ELSE rules.Estado
        END,
    FechaActualizacion = SYSDATETIME()
FROM Audit.ReglaAuditoria AS rules
WHERE rules.CodigoRegla IN ('AUD-CAMBIO-TARDIO', 'AUD-NOTA-CREDITO', 'AUD-CAMBIO-VENDEDOR', 'AUD-POST-CIERRE');
GO

SELECT
    cases.CodigoRegla,
    rules.Estado AS EstadoRegla,
    COUNT_BIG(*) AS Casos,
    SUM(CASE WHEN cases.EstadoValidacion IN ('ok', 'tecnico_ok') THEN 1 ELSE 0 END) AS CasosOk,
    SUM(CASE WHEN cases.ResultadoEsperado = cases.ResultadoVista THEN 1 ELSE 0 END) AS Coinciden
FROM Audit.CasoValidacionAuditoria AS cases
INNER JOIN Audit.ReglaAuditoria AS rules
    ON rules.CodigoRegla = cases.CodigoRegla
GROUP BY cases.CodigoRegla, rules.Estado
ORDER BY cases.CodigoRegla;
GO
