/*
    WallyAgent 4.0
    Script 13 - Crear tabla dbo.ColaboradorTurno y vista dbo.VwColaboradoresTurno.
*/

USE WallyBD;
GO

IF OBJECT_ID('dbo.ColaboradorTurno', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.ColaboradorTurno (
        idEmpleado INT PRIMARY KEY,
        Turno VARCHAR(20) NOT NULL CONSTRAINT CK_ColaboradorTurno_Turno CHECK (Turno IN ('Diurno', 'Mixto', 'Completo', 'Nocturno')),
        FechaActualizado DATETIME NOT NULL DEFAULT GETDATE()
    );
END;
GO

CREATE OR ALTER VIEW dbo.VwColaboradoresTurno
AS
SELECT 
    e.idEmpleado AS CODIGO,
    COALESCE(
        NULLIF(e.DoctoID COLLATE DATABASE_DEFAULT, ''), 
        NULLIF(e.IDT COLLATE DATABASE_DEFAULT, ''), 
        'No registrado'
    ) AS Documento,
    e.btFecha AS [Fecha Creacion],
    LTRIM(RTRIM(ISNULL(e.Nombres COLLATE DATABASE_DEFAULT, '') + ' ' + ISNULL(e.Apellidos COLLATE DATABASE_DEFAULT, ''))) AS Nombre,
    p.Descripcion COLLATE DATABASE_DEFAULT AS Cargo,
    s.Descripcion COLLATE DATABASE_DEFAULT AS Sucursal,
    ISNULL(t.Turno COLLATE DATABASE_DEFAULT, 'Diurno') AS Turno,
    (
        SELECT MIN(f.Fecha) 
        FROM dbo.VwFacturaConImpuesto f 
        WHERE TRY_CONVERT(int, f.IdVendedor) = e.idEmpleado
    ) AS [Fecha de alta],
    e.FlagStatus AS Activo
FROM StudioF.dbo.Empleado e
LEFT JOIN StudioF.dbo.Puesto p ON e.idPuesto = p.idPuesto
LEFT JOIN StudioF.dbo.Sucursal s ON e.IdSucursal = s.idSucursal
LEFT JOIN dbo.ColaboradorTurno t ON e.idEmpleado = t.idEmpleado;
GO
