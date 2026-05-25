/*
    WallyAgent 4.0
    Script 11 - Indices de rendimiento sobre tablas Mirror en WallyBD.

    No toca StudioF. Solo optimiza consultas de la app sobre WallyBD.
*/

USE WallyBD;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'Mirror.FacturaConImpuesto') AND name = N'IX_Mirror_Factura_Fecha_Sucursal')
BEGIN
    CREATE INDEX IX_Mirror_Factura_Fecha_Sucursal
    ON Mirror.FacturaConImpuesto (Fecha, Sucursal)
    INCLUDE (Numero, Trn, VentaNetaQ, Unidades, CostoTotal, Vendedor, Referencia, Linea, DescripTipoPrenda, CodEmbarqueAbreviado);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'Mirror.FacturaConImpuesto') AND name = N'IX_Mirror_Factura_Referencia_Fecha')
BEGIN
    CREATE INDEX IX_Mirror_Factura_Referencia_Fecha
    ON Mirror.FacturaConImpuesto (Referencia, Fecha)
    INCLUDE (Sucursal, Numero, VentaNetaQ, Unidades, Vendedor, CodEmbarqueAbreviado);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'Mirror.FacturaConImpuesto') AND name = N'IX_Mirror_Factura_Embarque_Fecha')
BEGIN
    CREATE INDEX IX_Mirror_Factura_Embarque_Fecha
    ON Mirror.FacturaConImpuesto (CodEmbarqueAbreviado, Fecha)
    INCLUDE (Sucursal, Referencia, VentaNetaQ, Unidades, Linea, DescripTipoPrenda);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'Mirror.Existencia') AND name = N'IX_Mirror_Existencia_Sucursal_Referencia')
BEGIN
    CREATE INDEX IX_Mirror_Existencia_Sucursal_Referencia
    ON Mirror.Existencia (Sucursal, Referencia)
    INCLUDE (CodBarras, CodEmbarqueAbreviado, Linea, DescripTipoPrenda, Talla, Color, ExistenciaFisica, ExistenciaDisponible, TVida);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'Mirror.Existencia') AND name = N'IX_Mirror_Existencia_Embarque_Linea')
BEGIN
    CREATE INDEX IX_Mirror_Existencia_Embarque_Linea
    ON Mirror.Existencia (CodEmbarqueAbreviado, Linea)
    INCLUDE (Sucursal, Referencia, ExistenciaFisica, ExistenciaDisponible, TVida);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'Mirror.EntradasInventario') AND name = N'IX_Mirror_Entradas_Fecha_Embarque')
BEGIN
    CREATE INDEX IX_Mirror_Entradas_Fecha_Embarque
    ON Mirror.EntradasInventario (FechaEntrada, CodEmbarqueAbreviado)
    INCLUDE (Sucursal, Referencia, Linea, DescripTipoPrenda, UnidadesEntrada);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'Mirror.EntradasInventario') AND name = N'IX_Mirror_Entradas_Referencia_Fecha')
BEGIN
    CREATE INDEX IX_Mirror_Entradas_Referencia_Fecha
    ON Mirror.EntradasInventario (Referencia, FechaEntrada)
    INCLUDE (Sucursal, CodEmbarqueAbreviado, UnidadesEntrada);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'Mirror.ClienteResumenCRM') AND name = N'IX_Mirror_CRM_Dias_Venta')
BEGIN
    CREATE INDEX IX_Mirror_CRM_Dias_Venta
    ON Mirror.ClienteResumenCRM (DiasSinCompra, VentaNetaTotal)
    INCLUDE (NumeroCliente, Cliente, Telefono, Celular, Email, SucursalPreferida, FechaUltimaCompra);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'Mirror.MovimientoInv') AND name = N'IX_Mirror_Movimiento_Fecha')
BEGIN
    CREATE INDEX IX_Mirror_Movimiento_Fecha
    ON Mirror.MovimientoInv (Fecha, idTransaccionInv)
    INCLUDE (idSucursal, idMovimientoInv, Numero, idUsuario, idMovimientoInvRef, idEmpleadoCajero, Total);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'Mirror.MovimientoInv') AND name = N'IX_Mirror_Movimiento_Id')
BEGIN
    CREATE INDEX IX_Mirror_Movimiento_Id
    ON Mirror.MovimientoInv (idSucursal, idMovimientoInv)
    INCLUDE (Numero, Fecha, idUsuario, idTransaccionInv, idMovimientoInvRef, idEmpleadoCajero, Total);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'Mirror.BITMovimientoInv') AND name = N'IX_Mirror_BITMovimiento_Id_Fecha')
BEGIN
    CREATE INDEX IX_Mirror_BITMovimiento_Id_Fecha
    ON Mirror.BITMovimientoInv (idSucursal, idMovimientoInv, btFecha)
    INCLUDE (idEmpleado, btLogin, Total);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'Mirror.MovimientoInvPago') AND name = N'IX_Mirror_MovimientoPago_Id_Fecha')
BEGIN
    CREATE INDEX IX_Mirror_MovimientoPago_Id_Fecha
    ON Mirror.MovimientoInvPago (idSucursal, idMovimientoInv, btFecha);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'Mirror.MovCajaCierre') AND name = N'IX_Mirror_MovCajaCierre_Sucursal_Fecha')
BEGIN
    CREATE INDEX IX_Mirror_MovCajaCierre_Sucursal_Fecha
    ON Mirror.MovCajaCierre (idSucursal, btFecha);
END;
GO

SELECT
    OBJECT_SCHEMA_NAME(object_id) AS SchemaName,
    OBJECT_NAME(object_id) AS TableName,
    name AS IndexName
FROM sys.indexes
WHERE OBJECT_SCHEMA_NAME(object_id) = 'Mirror'
  AND name IS NOT NULL
ORDER BY TableName, IndexName;
GO
