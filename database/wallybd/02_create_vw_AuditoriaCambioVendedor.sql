/*
    WallyAgent 4.0
    Script 02 - Vista dbo.vw_AuditoriaCambioVendedor en WallyBD.

    Fuente: tablas Mirror.* de WallyBD, alimentadas administrativamente desde StudioF.
    Destino: WallyBD.

    Validacion pendiente en produccion:
    - Confirmar que BITMovimientoInv.idEmpleado representa el vendedor historico.
    - Confirmar que MovimientoInv.idEmpleadoCajero representa el vendedor/cajero actual
      que debe compararse con BITMovimientoInv si el negocio lo requiere.
    - Confirmar si MovCajaCierre.btFecha registra el cierre en la misma fecha de venta
      o si algunas tiendas cierran despues de medianoche. La regla actual usa la fecha
      del documento como jornada.
    - FlagCambioPosteriorPago usa tolerancia de 60 segundos para evitar falsos positivos
      por registros automaticos inmediatamente posteriores al pago.
    - FlagCambioTardio excluye transferencias operativas entre sucursales:
      idTransaccionInv 4 = Exporta a Sucursal, 5 = Importa de Sucursal.
    - FlagPosibleNotaCredito usa idTransaccionInv = 10, validado en catalogo
      StudioF.dbo.TransaccionInv como "Nota de credito cliente".
    - Las banderas de auditoria excluyen pedidos: idTransaccionInv = 31.
      Negocio confirmo que Pedido no debe auditarse.
*/

USE WallyBD;
GO

CREATE OR ALTER VIEW dbo.vw_AuditoriaCambioVendedor
AS
WITH BitOrdenado AS (
    SELECT
        bit.idSucursal,
        bit.idMovimientoInv,
        bit.idEmpleado,
        bit.btFecha,
        bit.btLogin,
        bit.Total,
        ROW_NUMBER() OVER (
            PARTITION BY bit.idSucursal, bit.idMovimientoInv
            ORDER BY bit.btFecha ASC
        ) AS rn_primero,
        ROW_NUMBER() OVER (
            PARTITION BY bit.idSucursal, bit.idMovimientoInv
            ORDER BY bit.btFecha DESC
        ) AS rn_ultimo
    FROM Mirror.BITMovimientoInv AS bit
),
BitAgregado AS (
    SELECT
        idSucursal,
        idMovimientoInv,
        COUNT_BIG(*) AS CantidadEventosBIT,
        MIN(btFecha) AS FechaPrimerRegistro,
        MAX(btFecha) AS FechaUltimoCambio,
        CASE WHEN COUNT_BIG(*) > 0 THEN COUNT_BIG(*) - 1 ELSE 0 END AS CantidadCambiosDetectados
    FROM Mirror.BITMovimientoInv
    GROUP BY idSucursal, idMovimientoInv
),
BitPrimero AS (
    SELECT
        idSucursal,
        idMovimientoInv,
        idEmpleado AS VendedorInicial,
        btLogin AS UsuarioPrimerRegistro,
        Total AS TotalPrimerRegistro
    FROM BitOrdenado
    WHERE rn_primero = 1
),
BitUltimo AS (
    SELECT
        idSucursal,
        idMovimientoInv,
        idEmpleado AS VendedorFinalBIT,
        btLogin AS UsuarioUltimoCambio,
        Total AS TotalUltimoRegistro
    FROM BitOrdenado
    WHERE rn_ultimo = 1
),
Pagos AS (
    SELECT
        idSucursal,
        idMovimientoInv,
        MIN(btFecha) AS FechaPrimerPago,
        MAX(btFecha) AS FechaUltimoPago,
        COUNT_BIG(*) AS CantidadPagos
    FROM Mirror.MovimientoInvPago
    GROUP BY idSucursal, idMovimientoInv
),
Cierres AS (
    SELECT
        mov.idSucursal,
        mov.idMovimientoInv,
        MAX(cierre.btFecha) AS FechaUltimoCierre
    FROM Mirror.MovimientoInv AS mov
    LEFT JOIN Mirror.MovCajaCierre AS cierre
        ON cierre.idSucursal = mov.idSucursal
       AND CAST(cierre.btFecha AS date) = CAST(mov.Fecha AS date)
    GROUP BY mov.idSucursal, mov.idMovimientoInv
),
Core AS (
    SELECT
        mov.idSucursal,
        CASE
            WHEN UPPER(LTRIM(RTRIM(ISNULL(suc.Descripcion COLLATE DATABASE_DEFAULT, '')))) = 'PARQUE LAS AMERICAS' THEN 'Americas'
            ELSE LTRIM(RTRIM(ISNULL(suc.Descripcion COLLATE DATABASE_DEFAULT, '')))
        END AS Sucursal,
        mov.idMovimientoInv,
        mov.Numero,
        mov.Fecha,
        mov.idUsuario,
        COALESCE(
            NULLIF(
                CASE
                    WHEN LTRIM(RTRIM(ISNULL(emp_usuario.Nombres COLLATE DATABASE_DEFAULT, ''))) =
                         LTRIM(RTRIM(ISNULL(emp_usuario.Apellidos COLLATE DATABASE_DEFAULT, '')))
                    THEN LTRIM(RTRIM(ISNULL(emp_usuario.Nombres COLLATE DATABASE_DEFAULT, '')))
                    ELSE LTRIM(RTRIM(ISNULL(emp_usuario.Nombres COLLATE DATABASE_DEFAULT, '') + ' ' + ISNULL(emp_usuario.Apellidos COLLATE DATABASE_DEFAULT, '')))
                END,
                ''
            ),
            NULLIF(
                CASE
                    WHEN LTRIM(RTRIM(ISNULL(usuario.Nombres COLLATE DATABASE_DEFAULT, ''))) =
                         LTRIM(RTRIM(ISNULL(usuario.Apellidos COLLATE DATABASE_DEFAULT, '')))
                    THEN LTRIM(RTRIM(ISNULL(usuario.Nombres COLLATE DATABASE_DEFAULT, '')))
                    ELSE LTRIM(RTRIM(ISNULL(usuario.Nombres COLLATE DATABASE_DEFAULT, '') + ' ' + ISNULL(usuario.Apellidos COLLATE DATABASE_DEFAULT, '')))
                END,
                ''
            ),
            NULLIF(LTRIM(RTRIM(usuario.Login COLLATE DATABASE_DEFAULT)), ''),
            CONVERT(varchar(20), mov.idUsuario)
        ) AS NombreEmpleadoUsuario,
        mov.idTransaccionInv,
        trans.Descripcion AS TransaccionInvDescripcion,
        mov.idMovimientoInvRef,
        mov.idEmpleadoCajero,
        COALESCE(
            NULLIF(
                CASE
                    WHEN LTRIM(RTRIM(ISNULL(cajero.Nombres COLLATE DATABASE_DEFAULT, ''))) =
                         LTRIM(RTRIM(ISNULL(cajero.Apellidos COLLATE DATABASE_DEFAULT, '')))
                    THEN LTRIM(RTRIM(ISNULL(cajero.Nombres COLLATE DATABASE_DEFAULT, '')))
                    ELSE LTRIM(RTRIM(ISNULL(cajero.Nombres COLLATE DATABASE_DEFAULT, '') + ' ' + ISNULL(cajero.Apellidos COLLATE DATABASE_DEFAULT, '')))
                END,
                ''
            ),
            CONVERT(varchar(20), mov.idEmpleadoCajero)
        ) AS NombreCaja,
        mov.Total,
        primero.VendedorInicial,
        COALESCE(
            NULLIF(
                CASE
                    WHEN LTRIM(RTRIM(ISNULL(vendedor_inicial.Nombres COLLATE DATABASE_DEFAULT, ''))) =
                         LTRIM(RTRIM(ISNULL(vendedor_inicial.Apellidos COLLATE DATABASE_DEFAULT, '')))
                    THEN LTRIM(RTRIM(ISNULL(vendedor_inicial.Nombres COLLATE DATABASE_DEFAULT, '')))
                    ELSE LTRIM(RTRIM(ISNULL(vendedor_inicial.Nombres COLLATE DATABASE_DEFAULT, '') + ' ' + ISNULL(vendedor_inicial.Apellidos COLLATE DATABASE_DEFAULT, '')))
                END,
                ''
            ),
            CONVERT(varchar(20), primero.VendedorInicial)
        ) AS NombreVendedorInicial,
        ultimo.VendedorFinalBIT,
        COALESCE(
            NULLIF(
                CASE
                    WHEN LTRIM(RTRIM(ISNULL(vendedor_final.Nombres COLLATE DATABASE_DEFAULT, ''))) =
                         LTRIM(RTRIM(ISNULL(vendedor_final.Apellidos COLLATE DATABASE_DEFAULT, '')))
                    THEN LTRIM(RTRIM(ISNULL(vendedor_final.Nombres COLLATE DATABASE_DEFAULT, '')))
                    ELSE LTRIM(RTRIM(ISNULL(vendedor_final.Nombres COLLATE DATABASE_DEFAULT, '') + ' ' + ISNULL(vendedor_final.Apellidos COLLATE DATABASE_DEFAULT, '')))
                END,
                ''
            ),
            CONVERT(varchar(20), ultimo.VendedorFinalBIT)
        ) AS NombreVendedorFinal,
        CAST(
            CASE
                WHEN primero.VendedorInicial IS NOT NULL
                 AND ultimo.VendedorFinalBIT IS NOT NULL
                 AND mov.idTransaccionInv <> 31
                 AND ISNULL(primero.VendedorInicial, -1) <> ISNULL(ultimo.VendedorFinalBIT, -1)
                THEN 1 ELSE 0
            END AS bit
        ) AS FlagCambioVendedor,
        agregado.FechaPrimerRegistro,
        primero.UsuarioPrimerRegistro,
        agregado.FechaUltimoCambio,
        ultimo.UsuarioUltimoCambio,
        pagos.FechaPrimerPago,
        pagos.FechaUltimoPago,
        ISNULL(CONVERT(bigint, pagos.CantidadPagos), 0) AS CantidadPagos,
        CASE
            WHEN agregado.FechaUltimoCambio IS NULL OR pagos.FechaUltimoPago IS NULL THEN NULL
            ELSE DATEDIFF(SECOND, pagos.FechaUltimoPago, agregado.FechaUltimoCambio)
        END AS SegundosDespuesPago,
        CAST(
            CASE
                WHEN agregado.FechaUltimoCambio IS NOT NULL
                 AND pagos.FechaUltimoPago IS NOT NULL
                 AND mov.idTransaccionInv <> 31
                 AND DATEDIFF(SECOND, pagos.FechaUltimoPago, agregado.FechaUltimoCambio) > 60
                THEN 1 ELSE 0
            END AS bit
        ) AS FlagCambioPosteriorPago,
        cierres.FechaUltimoCierre,
        CAST(
            CASE
                WHEN agregado.FechaUltimoCambio IS NOT NULL
                 AND cierres.FechaUltimoCierre IS NOT NULL
                 AND mov.idTransaccionInv <> 31
                 AND agregado.FechaUltimoCambio > cierres.FechaUltimoCierre
                THEN 1 ELSE 0
            END AS bit
        ) AS FlagCambioPosteriorCierre,
        ISNULL(CONVERT(bigint, agregado.CantidadEventosBIT), 0) AS CantidadEventosBIT,
        ISNULL(CONVERT(bigint, agregado.CantidadCambiosDetectados), 0) AS CantidadCambiosDetectados,
        CASE
            WHEN agregado.FechaPrimerRegistro IS NULL OR agregado.FechaUltimoCambio IS NULL THEN NULL
            ELSE DATEDIFF(MINUTE, agregado.FechaPrimerRegistro, agregado.FechaUltimoCambio)
        END AS MinutosHastaUltimoCambio,
        CAST(
            CASE
                WHEN agregado.FechaPrimerRegistro IS NOT NULL
                 AND agregado.FechaUltimoCambio IS NOT NULL
                 AND mov.idTransaccionInv NOT IN (4, 5)
                 AND mov.idTransaccionInv <> 31
                 AND DATEDIFF(MINUTE, agregado.FechaPrimerRegistro, agregado.FechaUltimoCambio) > 60
                THEN 1 ELSE 0
            END AS bit
        ) AS FlagCambioTardio,
        CAST(CASE WHEN mov.idTransaccionInv = 10 THEN 1 ELSE 0 END AS bit) AS FlagPosibleNotaCredito
    FROM Mirror.MovimientoInv AS mov
    LEFT JOIN Mirror.Sucursal AS suc
        ON suc.idSucursal = mov.idSucursal
    LEFT JOIN Mirror.Usuario AS usuario
        ON usuario.idUsuario = mov.idUsuario
    LEFT JOIN Mirror.Empleado AS emp_usuario
        ON emp_usuario.idEmpleado = usuario.idEmpleado
    LEFT JOIN Mirror.Empleado AS cajero
        ON cajero.idEmpleado = mov.idEmpleadoCajero
    LEFT JOIN Mirror.TransaccionInv AS trans
        ON trans.idTransaccionInv = mov.idTransaccionInv
    LEFT JOIN BitAgregado AS agregado
        ON agregado.idSucursal = mov.idSucursal
       AND agregado.idMovimientoInv = mov.idMovimientoInv
    LEFT JOIN BitPrimero AS primero
        ON primero.idSucursal = mov.idSucursal
       AND primero.idMovimientoInv = mov.idMovimientoInv
    LEFT JOIN BitUltimo AS ultimo
        ON ultimo.idSucursal = mov.idSucursal
       AND ultimo.idMovimientoInv = mov.idMovimientoInv
    LEFT JOIN Mirror.Empleado AS vendedor_inicial
        ON vendedor_inicial.idEmpleado = primero.VendedorInicial
    LEFT JOIN Mirror.Empleado AS vendedor_final
        ON vendedor_final.idEmpleado = ultimo.VendedorFinalBIT
    LEFT JOIN Pagos AS pagos
        ON pagos.idSucursal = mov.idSucursal
       AND pagos.idMovimientoInv = mov.idMovimientoInv
    LEFT JOIN Cierres AS cierres
        ON cierres.idSucursal = mov.idSucursal
       AND cierres.idMovimientoInv = mov.idMovimientoInv
)
SELECT
    Core.*,
    COALESCE(
        NULLIF(
            STUFF(
                CONCAT(
                    CASE WHEN FlagCambioVendedor = 1 THEN '; Cambio de vendedor' ELSE '' END,
                    CASE WHEN FlagCambioPosteriorPago = 1 THEN '; Cambio posterior al pago' ELSE '' END,
                    CASE WHEN FlagCambioPosteriorCierre = 1 THEN '; Cambio posterior al cierre' ELSE '' END,
                    CASE WHEN FlagCambioTardio = 1 THEN '; Cambio tardio' ELSE '' END,
                    CASE WHEN FlagPosibleNotaCredito = 1 THEN '; Nota de credito' ELSE '' END,
                    CASE
                        WHEN idTransaccionInv IN (4, 5)
                         AND FlagCambioVendedor = 0
                         AND FlagCambioPosteriorPago = 0
                         AND FlagPosibleNotaCredito = 0
                        THEN '; Traslado operativo'
                        ELSE ''
                    END
                ),
                1,
                2,
                ''
            ),
            ''
        ),
        'Sin alerta'
    ) AS TipoAlerta,
    CASE
        WHEN FlagCambioVendedor = 1 OR FlagCambioPosteriorPago = 1 THEN 'Alto'
        WHEN idTransaccionInv IN (4, 5)
         AND FlagCambioVendedor = 0
         AND FlagCambioPosteriorPago = 0
         AND FlagPosibleNotaCredito = 0 THEN 'Operativo'
        WHEN FlagPosibleNotaCredito = 1
         AND (ABS(ISNULL(Total, 0)) >= 1000 OR FlagCambioPosteriorCierre = 1) THEN 'Medio'
        WHEN FlagCambioPosteriorCierre = 1 THEN 'Medio'
        WHEN FlagPosibleNotaCredito = 1 OR FlagCambioTardio = 1 THEN 'Bajo'
        ELSE 'Operativo'
    END AS NivelRiesgo,
    CAST(
        CASE
            WHEN FlagCambioVendedor = 1 OR FlagCambioPosteriorPago = 1 THEN 1
            WHEN FlagPosibleNotaCredito = 1
             AND (ABS(ISNULL(Total, 0)) >= 1000 OR FlagCambioPosteriorCierre = 1) THEN 1
            ELSE 0
        END AS bit
    ) AS EsRiesgoFraude
FROM Core;
GO

/*
    Indices recomendados para evaluar con el DBA.
    No se ejecutan automaticamente. Evaluar sobre tablas Mirror si el volumen
    crece y las consultas de auditoria necesitan optimizacion.

CREATE INDEX IX_BITMovimientoInv_Auditoria
ON Mirror.BITMovimientoInv
(
    idSucursal,
    idMovimientoInv,
    btFecha
)
INCLUDE
(
    idEmpleado,
    btLogin,
    Total
);

CREATE INDEX IX_MovimientoInvPago_Auditoria
ON Mirror.MovimientoInvPago
(
    idSucursal,
    idMovimientoInv,
    btFecha
);
*/
