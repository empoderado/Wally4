/*
    WallyAgent 4.0
    Script 07 - Semilla de reglas de auditoria.

    Puede ejecutarse varias veces. No duplica reglas existentes.
*/

USE WallyBD;
GO

MERGE Audit.ReglaAuditoria AS target
USING (
    VALUES
        (
            'AUD-CAMBIO-VENDEDOR',
            'Cambio de vendedor',
            'Compara el primer vendedor historico contra el ultimo vendedor historico registrado en BITMovimientoInv. Excluye pedidos idTransaccionInv = 31 por decision de negocio.',
            'FlagCambioVendedor',
            'validacion_funcional_ok'
        ),
        (
            'AUD-POST-PAGO',
            'Cambio posterior al pago',
            'Detecta documentos cuyo ultimo cambio BIT ocurre despues del ultimo pago registrado. Excluye pedidos idTransaccionInv = 31.',
            'FlagCambioPosteriorPago',
            'pendiente_validacion'
        ),
        (
            'AUD-POST-CIERRE',
            'Cambio posterior al cierre',
            'Detecta documentos cuyo ultimo cambio BIT real ocurre despues del cierre de la misma jornada y sucursal. Excluye pedidos y transferencias operativas.',
            'FlagCambioPosteriorCierre',
            'validacion_funcional_ok'
        ),
        (
            'AUD-CAMBIO-TARDIO',
            'Cambio tardio',
            'Detecta documentos con mas de 60 minutos entre primer registro BIT y ultimo cambio BIT, excluyendo transferencias operativas entre sucursales y pedidos.',
            'FlagCambioTardio',
            'pendiente_validacion'
        ),
        (
            'AUD-NOTA-CREDITO',
            'Posible nota credito',
            'Detecta notas de credito de cliente por catalogo de transaccion idTransaccionInv = 10.',
            'FlagPosibleNotaCredito',
            'pendiente_validacion'
        )
) AS source(CodigoRegla, NombreRegla, Descripcion, CampoVista, Estado)
ON target.CodigoRegla = source.CodigoRegla
WHEN MATCHED THEN
    UPDATE SET
        NombreRegla = source.NombreRegla,
        Descripcion = source.Descripcion,
        CampoVista = source.CampoVista,
        FechaActualizacion = SYSDATETIME()
WHEN NOT MATCHED THEN
    INSERT (CodigoRegla, NombreRegla, Descripcion, CampoVista, Estado)
    VALUES (source.CodigoRegla, source.NombreRegla, source.Descripcion, source.CampoVista, source.Estado);
GO

SELECT *
FROM Audit.ReglaAuditoria
ORDER BY CodigoRegla;
GO
