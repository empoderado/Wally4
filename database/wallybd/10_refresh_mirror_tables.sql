/*
    WallyAgent 4.0
    Script 10 - Refrescar tablas Mirror desde StudioF con bitacora.

    Este script es administrativo. La app UX no consulta StudioF; solo consulta
    las vistas dbo.* de WallyBD, que leen tablas Mirror.*.
*/

USE WallyBD;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

DECLARE @IdRefresco bigint;
DECLARE @IdDetalle bigint;
DECLARE @FilasAntes bigint;
DECLARE @FilasFuente bigint;
DECLARE @FilasFinal bigint;

INSERT INTO Admin.RefrescoMirrorLog (Estado)
VALUES ('iniciado');

SET @IdRefresco = CONVERT(bigint, SCOPE_IDENTITY());

BEGIN TRY
    /* Mirror.FacturaConImpuesto */
    SELECT @FilasAntes = COUNT_BIG(*) FROM Mirror.FacturaConImpuesto;
    SELECT @FilasFuente = COUNT_BIG(*) FROM Source.VwFacturaConImpuesto;
    INSERT INTO Admin.RefrescoMirrorDetalle (IdRefresco, Tabla, FilasAntes, FilasFuente)
    VALUES (@IdRefresco, 'Mirror.FacturaConImpuesto', @FilasAntes, @FilasFuente);
    SET @IdDetalle = CONVERT(bigint, SCOPE_IDENTITY());
    IF @FilasFuente = 0 THROW 51001, 'Fuente vacia: Source.VwFacturaConImpuesto', 1;
    BEGIN TRAN;
        TRUNCATE TABLE Mirror.FacturaConImpuesto;
        INSERT INTO Mirror.FacturaConImpuesto SELECT * FROM Source.VwFacturaConImpuesto;
        SELECT @FilasFinal = COUNT_BIG(*) FROM Mirror.FacturaConImpuesto;
    COMMIT;
    UPDATE Admin.RefrescoMirrorDetalle SET FechaFin = SYSDATETIME(), Estado = 'ok', FilasInsertadas = @FilasFinal, FilasFinal = @FilasFinal WHERE IdDetalle = @IdDetalle;

    /* Mirror.Existencia */
    SELECT @FilasAntes = COUNT_BIG(*) FROM Mirror.Existencia;
    SELECT @FilasFuente = COUNT_BIG(*) FROM Source.VwExistencia;
    INSERT INTO Admin.RefrescoMirrorDetalle (IdRefresco, Tabla, FilasAntes, FilasFuente)
    VALUES (@IdRefresco, 'Mirror.Existencia', @FilasAntes, @FilasFuente);
    SET @IdDetalle = CONVERT(bigint, SCOPE_IDENTITY());
    IF @FilasFuente = 0 THROW 51002, 'Fuente vacia: Source.VwExistencia', 1;
    BEGIN TRAN;
        TRUNCATE TABLE Mirror.Existencia;
        INSERT INTO Mirror.Existencia SELECT * FROM Source.VwExistencia;
        SELECT @FilasFinal = COUNT_BIG(*) FROM Mirror.Existencia;
    COMMIT;
    UPDATE Admin.RefrescoMirrorDetalle SET FechaFin = SYSDATETIME(), Estado = 'ok', FilasInsertadas = @FilasFinal, FilasFinal = @FilasFinal WHERE IdDetalle = @IdDetalle;

    /* Mirror.EntradasInventario */
    SELECT @FilasAntes = COUNT_BIG(*) FROM Mirror.EntradasInventario;
    SELECT @FilasFuente = COUNT_BIG(*) FROM Source.VwEntradasInventario;
    INSERT INTO Admin.RefrescoMirrorDetalle (IdRefresco, Tabla, FilasAntes, FilasFuente)
    VALUES (@IdRefresco, 'Mirror.EntradasInventario', @FilasAntes, @FilasFuente);
    SET @IdDetalle = CONVERT(bigint, SCOPE_IDENTITY());
    IF @FilasFuente = 0 THROW 51003, 'Fuente vacia: Source.VwEntradasInventario', 1;
    BEGIN TRAN;
        TRUNCATE TABLE Mirror.EntradasInventario;
        INSERT INTO Mirror.EntradasInventario
        SELECT
            FechaEntrada,
            CAST(FechaEntrada AS datetime) AS FechaHoraEntrada,
            idSucursal,
            Sucursal,
            idArticulo,
            NombreTallaColor,
            Referencia,
            CodBarras,
            DescripcionArticulo,
            CodEmbarque,
            CodEmbarqueAbreviado,
            Linea,
            DescripTipoPrenda,
            Talla,
            Color,
            SiglaTransaccion,
            Transaccion,
            UnidadesEntrada
        FROM Source.VwEntradasInventario;
        SELECT @FilasFinal = COUNT_BIG(*) FROM Mirror.EntradasInventario;
    COMMIT;
    UPDATE Admin.RefrescoMirrorDetalle SET FechaFin = SYSDATETIME(), Estado = 'ok', FilasInsertadas = @FilasFinal, FilasFinal = @FilasFinal WHERE IdDetalle = @IdDetalle;

    /* Mirror.ClienteResumenCRM */
    SELECT @FilasAntes = COUNT_BIG(*) FROM Mirror.ClienteResumenCRM;
    SELECT @FilasFuente = COUNT_BIG(*) FROM Source.VwClienteResumenCRM;
    INSERT INTO Admin.RefrescoMirrorDetalle (IdRefresco, Tabla, FilasAntes, FilasFuente)
    VALUES (@IdRefresco, 'Mirror.ClienteResumenCRM', @FilasAntes, @FilasFuente);
    SET @IdDetalle = CONVERT(bigint, SCOPE_IDENTITY());
    IF @FilasFuente = 0 THROW 51004, 'Fuente vacia: Source.VwClienteResumenCRM', 1;
    BEGIN TRAN;
        TRUNCATE TABLE Mirror.ClienteResumenCRM;
        INSERT INTO Mirror.ClienteResumenCRM SELECT * FROM Source.VwClienteResumenCRM;
        SELECT @FilasFinal = COUNT_BIG(*) FROM Mirror.ClienteResumenCRM;
    COMMIT;
    UPDATE Admin.RefrescoMirrorDetalle SET FechaFin = SYSDATETIME(), Estado = 'ok', FilasInsertadas = @FilasFinal, FilasFinal = @FilasFinal WHERE IdDetalle = @IdDetalle;

    /* Mirror.MovimientoInv */
    SELECT @FilasAntes = COUNT_BIG(*) FROM Mirror.MovimientoInv;
    SELECT @FilasFuente = COUNT_BIG(*) FROM StudioF.dbo.MovimientoInv;
    INSERT INTO Admin.RefrescoMirrorDetalle (IdRefresco, Tabla, FilasAntes, FilasFuente)
    VALUES (@IdRefresco, 'Mirror.MovimientoInv', @FilasAntes, @FilasFuente);
    SET @IdDetalle = CONVERT(bigint, SCOPE_IDENTITY());
    IF @FilasFuente = 0 THROW 51005, 'Fuente vacia: StudioF.dbo.MovimientoInv', 1;
    BEGIN TRAN;
        TRUNCATE TABLE Mirror.MovimientoInv;
        INSERT INTO Mirror.MovimientoInv
        SELECT idSucursal, idMovimientoInv, Numero, Fecha, idUsuario, idTransaccionInv, idMovimientoInvRef, idEmpleadoCajero, Total
        FROM StudioF.dbo.MovimientoInv;
        SELECT @FilasFinal = COUNT_BIG(*) FROM Mirror.MovimientoInv;
    COMMIT;
    UPDATE Admin.RefrescoMirrorDetalle SET FechaFin = SYSDATETIME(), Estado = 'ok', FilasInsertadas = @FilasFinal, FilasFinal = @FilasFinal WHERE IdDetalle = @IdDetalle;

    /* Mirror.BITMovimientoInv */
    SELECT @FilasAntes = COUNT_BIG(*) FROM Mirror.BITMovimientoInv;
    SELECT @FilasFuente = COUNT_BIG(*) FROM StudioF.dbo.BITMovimientoInv;
    INSERT INTO Admin.RefrescoMirrorDetalle (IdRefresco, Tabla, FilasAntes, FilasFuente)
    VALUES (@IdRefresco, 'Mirror.BITMovimientoInv', @FilasAntes, @FilasFuente);
    SET @IdDetalle = CONVERT(bigint, SCOPE_IDENTITY());
    IF @FilasFuente = 0 THROW 51006, 'Fuente vacia: StudioF.dbo.BITMovimientoInv', 1;
    BEGIN TRAN;
        TRUNCATE TABLE Mirror.BITMovimientoInv;
        INSERT INTO Mirror.BITMovimientoInv
        SELECT idSucursal, idMovimientoInv, idEmpleado, btFecha, btLogin, Total
        FROM StudioF.dbo.BITMovimientoInv;
        SELECT @FilasFinal = COUNT_BIG(*) FROM Mirror.BITMovimientoInv;
    COMMIT;
    UPDATE Admin.RefrescoMirrorDetalle SET FechaFin = SYSDATETIME(), Estado = 'ok', FilasInsertadas = @FilasFinal, FilasFinal = @FilasFinal WHERE IdDetalle = @IdDetalle;

    /* Mirror.MovimientoInvPago */
    SELECT @FilasAntes = COUNT_BIG(*) FROM Mirror.MovimientoInvPago;
    SELECT @FilasFuente = COUNT_BIG(*) FROM StudioF.dbo.MovimientoInvPago;
    INSERT INTO Admin.RefrescoMirrorDetalle (IdRefresco, Tabla, FilasAntes, FilasFuente)
    VALUES (@IdRefresco, 'Mirror.MovimientoInvPago', @FilasAntes, @FilasFuente);
    SET @IdDetalle = CONVERT(bigint, SCOPE_IDENTITY());
    IF @FilasFuente = 0 THROW 51007, 'Fuente vacia: StudioF.dbo.MovimientoInvPago', 1;
    BEGIN TRAN;
        TRUNCATE TABLE Mirror.MovimientoInvPago;
        INSERT INTO Mirror.MovimientoInvPago
        SELECT idSucursal, idMovimientoInv, btFecha
        FROM StudioF.dbo.MovimientoInvPago;
        SELECT @FilasFinal = COUNT_BIG(*) FROM Mirror.MovimientoInvPago;
    COMMIT;
    UPDATE Admin.RefrescoMirrorDetalle SET FechaFin = SYSDATETIME(), Estado = 'ok', FilasInsertadas = @FilasFinal, FilasFinal = @FilasFinal WHERE IdDetalle = @IdDetalle;

    /* Mirror.MovCajaCierre */
    SELECT @FilasAntes = COUNT_BIG(*) FROM Mirror.MovCajaCierre;
    SELECT @FilasFuente = COUNT_BIG(*) FROM StudioF.dbo.MovCajaCierre;
    INSERT INTO Admin.RefrescoMirrorDetalle (IdRefresco, Tabla, FilasAntes, FilasFuente)
    VALUES (@IdRefresco, 'Mirror.MovCajaCierre', @FilasAntes, @FilasFuente);
    SET @IdDetalle = CONVERT(bigint, SCOPE_IDENTITY());
    IF @FilasFuente = 0 THROW 51008, 'Fuente vacia: StudioF.dbo.MovCajaCierre', 1;
    BEGIN TRAN;
        TRUNCATE TABLE Mirror.MovCajaCierre;
        INSERT INTO Mirror.MovCajaCierre
        SELECT idSucursal, btFecha
        FROM StudioF.dbo.MovCajaCierre;
        SELECT @FilasFinal = COUNT_BIG(*) FROM Mirror.MovCajaCierre;
    COMMIT;
    UPDATE Admin.RefrescoMirrorDetalle SET FechaFin = SYSDATETIME(), Estado = 'ok', FilasInsertadas = @FilasFinal, FilasFinal = @FilasFinal WHERE IdDetalle = @IdDetalle;

    /* Mirror.TransaccionInv */
    SELECT @FilasAntes = COUNT_BIG(*) FROM Mirror.TransaccionInv;
    SELECT @FilasFuente = COUNT_BIG(*) FROM StudioF.dbo.TransaccionInv;
    INSERT INTO Admin.RefrescoMirrorDetalle (IdRefresco, Tabla, FilasAntes, FilasFuente)
    VALUES (@IdRefresco, 'Mirror.TransaccionInv', @FilasAntes, @FilasFuente);
    SET @IdDetalle = CONVERT(bigint, SCOPE_IDENTITY());
    IF @FilasFuente = 0 THROW 51009, 'Fuente vacia: StudioF.dbo.TransaccionInv', 1;
    BEGIN TRAN;
        TRUNCATE TABLE Mirror.TransaccionInv;
        INSERT INTO Mirror.TransaccionInv
        SELECT idTransaccionInv, Descripcion
        FROM StudioF.dbo.TransaccionInv;
        SELECT @FilasFinal = COUNT_BIG(*) FROM Mirror.TransaccionInv;
    COMMIT;
    UPDATE Admin.RefrescoMirrorDetalle SET FechaFin = SYSDATETIME(), Estado = 'ok', FilasInsertadas = @FilasFinal, FilasFinal = @FilasFinal WHERE IdDetalle = @IdDetalle;

    /* Mirror.Sucursal */
    SELECT @FilasAntes = COUNT_BIG(*) FROM Mirror.Sucursal;
    SELECT @FilasFuente = COUNT_BIG(*) FROM StudioF.dbo.Sucursal;
    INSERT INTO Admin.RefrescoMirrorDetalle (IdRefresco, Tabla, FilasAntes, FilasFuente)
    VALUES (@IdRefresco, 'Mirror.Sucursal', @FilasAntes, @FilasFuente);
    SET @IdDetalle = CONVERT(bigint, SCOPE_IDENTITY());
    IF @FilasFuente = 0 THROW 51010, 'Fuente vacia: StudioF.dbo.Sucursal', 1;
    BEGIN TRAN;
        TRUNCATE TABLE Mirror.Sucursal;
        INSERT INTO Mirror.Sucursal
        SELECT idSucursal, Descripcion
        FROM StudioF.dbo.Sucursal;
        SELECT @FilasFinal = COUNT_BIG(*) FROM Mirror.Sucursal;
    COMMIT;
    UPDATE Admin.RefrescoMirrorDetalle SET FechaFin = SYSDATETIME(), Estado = 'ok', FilasInsertadas = @FilasFinal, FilasFinal = @FilasFinal WHERE IdDetalle = @IdDetalle;

    /* Mirror.Usuario */
    SELECT @FilasAntes = COUNT_BIG(*) FROM Mirror.Usuario;
    SELECT @FilasFuente = COUNT_BIG(*) FROM StudioF.dbo.Usuario;
    INSERT INTO Admin.RefrescoMirrorDetalle (IdRefresco, Tabla, FilasAntes, FilasFuente)
    VALUES (@IdRefresco, 'Mirror.Usuario', @FilasAntes, @FilasFuente);
    SET @IdDetalle = CONVERT(bigint, SCOPE_IDENTITY());
    IF @FilasFuente = 0 THROW 51011, 'Fuente vacia: StudioF.dbo.Usuario', 1;
    BEGIN TRAN;
        TRUNCATE TABLE Mirror.Usuario;
        INSERT INTO Mirror.Usuario
        SELECT idUsuario, Nombres, Apellidos, Login, idEmpleado
        FROM StudioF.dbo.Usuario;
        SELECT @FilasFinal = COUNT_BIG(*) FROM Mirror.Usuario;
    COMMIT;
    UPDATE Admin.RefrescoMirrorDetalle SET FechaFin = SYSDATETIME(), Estado = 'ok', FilasInsertadas = @FilasFinal, FilasFinal = @FilasFinal WHERE IdDetalle = @IdDetalle;

    /* Mirror.Empleado */
    SELECT @FilasAntes = COUNT_BIG(*) FROM Mirror.Empleado;
    SELECT @FilasFuente = COUNT_BIG(*) FROM StudioF.dbo.Empleado;
    INSERT INTO Admin.RefrescoMirrorDetalle (IdRefresco, Tabla, FilasAntes, FilasFuente)
    VALUES (@IdRefresco, 'Mirror.Empleado', @FilasAntes, @FilasFuente);
    SET @IdDetalle = CONVERT(bigint, SCOPE_IDENTITY());
    IF @FilasFuente = 0 THROW 51012, 'Fuente vacia: StudioF.dbo.Empleado', 1;
    BEGIN TRAN;
        TRUNCATE TABLE Mirror.Empleado;
        INSERT INTO Mirror.Empleado
        SELECT idEmpleado, Nombres, Apellidos
        FROM StudioF.dbo.Empleado;
        SELECT @FilasFinal = COUNT_BIG(*) FROM Mirror.Empleado;
    COMMIT;
    UPDATE Admin.RefrescoMirrorDetalle SET FechaFin = SYSDATETIME(), Estado = 'ok', FilasInsertadas = @FilasFinal, FilasFinal = @FilasFinal WHERE IdDetalle = @IdDetalle;

    UPDATE Admin.RefrescoMirrorLog
    SET FechaFin = SYSDATETIME(),
        Estado = 'ok'
    WHERE IdRefresco = @IdRefresco;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
    BEGIN
        ROLLBACK;
    END;

    UPDATE Admin.RefrescoMirrorDetalle
    SET FechaFin = SYSDATETIME(),
        Estado = 'error',
        MensajeError = ERROR_MESSAGE()
    WHERE IdDetalle = @IdDetalle
      AND Estado = 'iniciado';

    UPDATE Admin.RefrescoMirrorLog
    SET FechaFin = SYSDATETIME(),
        Estado = 'error',
        MensajeError = ERROR_MESSAGE()
    WHERE IdRefresco = @IdRefresco;

    THROW;
END CATCH;

SELECT
    log.IdRefresco,
    log.FechaInicio,
    log.FechaFin,
    log.Estado,
    DATEDIFF(SECOND, log.FechaInicio, log.FechaFin) AS DuracionSegundos,
    log.EjecutadoPor
FROM Admin.RefrescoMirrorLog AS log
WHERE log.IdRefresco = @IdRefresco;

SELECT
    det.Tabla,
    det.Estado,
    det.FilasAntes,
    det.FilasFuente,
    det.FilasInsertadas,
    det.FilasFinal,
    DATEDIFF(SECOND, det.FechaInicio, det.FechaFin) AS DuracionSegundos
FROM Admin.RefrescoMirrorDetalle AS det
WHERE det.IdRefresco = @IdRefresco
ORDER BY det.IdDetalle;
GO
