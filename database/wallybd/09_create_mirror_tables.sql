/*
    WallyAgent 4.0
    Script 09 - Crear tablas materializadas Mirror en WallyBD.

    Objetivo:
    - Mantener el contrato publico dbo.Vw* para la app.
    - Separar runtime UX de accesos directos/cross-database a StudioF.
    - Permitir que solo procesos administrativos alimenten estas tablas desde StudioF.
*/

USE WallyBD;
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'Mirror')
BEGIN
    EXEC('CREATE SCHEMA Mirror');
END;
GO

IF OBJECT_ID('Mirror.FacturaConImpuesto', 'U') IS NULL
BEGIN
    SELECT TOP (0) *
    INTO Mirror.FacturaConImpuesto
    FROM Source.VwFacturaConImpuesto;
END;
GO

IF OBJECT_ID('Mirror.Existencia', 'U') IS NULL
BEGIN
    SELECT TOP (0) *
    INTO Mirror.Existencia
    FROM Source.VwExistencia;
END;
GO

IF OBJECT_ID('Mirror.EntradasInventario', 'U') IS NULL
BEGIN
    SELECT TOP (0)
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
    INTO Mirror.EntradasInventario
    FROM Source.VwEntradasInventario;
END;
GO

IF OBJECT_ID('Mirror.ClienteResumenCRM', 'U') IS NULL
BEGIN
    SELECT TOP (0) *
    INTO Mirror.ClienteResumenCRM
    FROM Source.VwClienteResumenCRM;
END;
GO

IF OBJECT_ID('Mirror.MovimientoInv', 'U') IS NULL
BEGIN
    SELECT TOP (0)
        idSucursal,
        idMovimientoInv,
        Numero,
        Fecha,
        idUsuario,
        idTransaccionInv,
        idMovimientoInvRef,
        idEmpleadoCajero,
        Total
    INTO Mirror.MovimientoInv
    FROM StudioF.dbo.MovimientoInv;
END;
GO

IF OBJECT_ID('Mirror.BITMovimientoInv', 'U') IS NULL
BEGIN
    SELECT TOP (0)
        idSucursal,
        idMovimientoInv,
        idEmpleado,
        btFecha,
        btLogin,
        Total
    INTO Mirror.BITMovimientoInv
    FROM StudioF.dbo.BITMovimientoInv;
END;
GO

IF OBJECT_ID('Mirror.MovimientoInvPago', 'U') IS NULL
BEGIN
    SELECT TOP (0)
        idSucursal,
        idMovimientoInv,
        btFecha
    INTO Mirror.MovimientoInvPago
    FROM StudioF.dbo.MovimientoInvPago;
END;
GO

IF OBJECT_ID('Mirror.MovCajaCierre', 'U') IS NULL
BEGIN
    SELECT TOP (0)
        idSucursal,
        btFecha
    INTO Mirror.MovCajaCierre
    FROM StudioF.dbo.MovCajaCierre;
END;
GO

IF OBJECT_ID('Mirror.TransaccionInv', 'U') IS NULL
BEGIN
    SELECT TOP (0)
        idTransaccionInv,
        Descripcion
    INTO Mirror.TransaccionInv
    FROM StudioF.dbo.TransaccionInv;
END;
GO

IF OBJECT_ID('Mirror.Sucursal', 'U') IS NULL
BEGIN
    SELECT TOP (0)
        idSucursal,
        Descripcion
    INTO Mirror.Sucursal
    FROM StudioF.dbo.Sucursal;
END;
GO

IF OBJECT_ID('Mirror.Usuario', 'U') IS NULL
BEGIN
    SELECT TOP (0)
        idUsuario,
        Nombres,
        Apellidos,
        Login,
        idEmpleado
    INTO Mirror.Usuario
    FROM StudioF.dbo.Usuario;
END;
GO

IF OBJECT_ID('Mirror.Empleado', 'U') IS NULL
BEGIN
    SELECT TOP (0)
        idEmpleado,
        Nombres,
        Apellidos
    INTO Mirror.Empleado
    FROM StudioF.dbo.Empleado;
END;
GO

SELECT
    s.name AS SchemaName,
    t.name AS TableName,
    SUM(p.rows) AS RowsApprox
FROM sys.tables AS t
INNER JOIN sys.schemas AS s
    ON s.schema_id = t.schema_id
LEFT JOIN sys.partitions AS p
    ON p.object_id = t.object_id
   AND p.index_id IN (0, 1)
WHERE s.name = 'Mirror'
GROUP BY s.name, t.name
ORDER BY t.name;
GO
