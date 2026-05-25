/*
    WallyAgent 4.0
    Script 06 - Tablas de validacion de reglas en WallyBD.

    Objetivo:
    - Validar reglas SQL en el ambiente final del servidor.
    - Registrar casos revisados contra SmartBit sin modificar StudioF.
    - Dejar evidencia funcional antes de congelar reglas de auditoria.
*/

USE WallyBD;
GO

IF SCHEMA_ID(N'Audit') IS NULL
BEGIN
    EXEC(N'CREATE SCHEMA Audit');
END
GO

IF OBJECT_ID(N'Audit.ReglaAuditoria', N'U') IS NULL
BEGIN
    CREATE TABLE Audit.ReglaAuditoria (
        CodigoRegla varchar(40) NOT NULL CONSTRAINT PK_ReglaAuditoria PRIMARY KEY,
        NombreRegla varchar(160) NOT NULL,
        Descripcion varchar(600) NOT NULL,
        CampoVista varchar(128) NOT NULL,
        Estado varchar(30) NOT NULL CONSTRAINT DF_ReglaAuditoria_Estado DEFAULT ('pendiente'),
        FechaCreacion datetime2(0) NOT NULL CONSTRAINT DF_ReglaAuditoria_FechaCreacion DEFAULT (SYSDATETIME()),
        FechaActualizacion datetime2(0) NULL
    );
END
GO

IF OBJECT_ID(N'Audit.CasoValidacionAuditoria', N'U') IS NULL
BEGIN
    CREATE TABLE Audit.CasoValidacionAuditoria (
        IdCasoValidacion int IDENTITY(1,1) NOT NULL CONSTRAINT PK_CasoValidacionAuditoria PRIMARY KEY,
        CodigoRegla varchar(40) NOT NULL,
        idSucursal int NULL,
        idMovimientoInv bigint NULL,
        Numero varchar(80) NULL,
        ResultadoEsperado bit NULL,
        ResultadoVista bit NULL,
        EstadoValidacion varchar(30) NOT NULL CONSTRAINT DF_CasoValidacionAuditoria_Estado DEFAULT ('pendiente'),
        Observacion varchar(1000) NULL,
        ValidadoPor varchar(120) NULL,
        FechaValidacion datetime2(0) NULL,
        FechaCreacion datetime2(0) NOT NULL CONSTRAINT DF_CasoValidacionAuditoria_FechaCreacion DEFAULT (SYSDATETIME()),
        CONSTRAINT FK_CasoValidacionAuditoria_Regla
            FOREIGN KEY (CodigoRegla) REFERENCES Audit.ReglaAuditoria(CodigoRegla)
    );
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = N'IX_CasoValidacionAuditoria_Numero'
      AND object_id = OBJECT_ID(N'Audit.CasoValidacionAuditoria')
)
BEGIN
    CREATE INDEX IX_CasoValidacionAuditoria_Numero
    ON Audit.CasoValidacionAuditoria (Numero)
    INCLUDE (CodigoRegla, EstadoValidacion, ResultadoEsperado, ResultadoVista);
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = N'IX_CasoValidacionAuditoria_Movimiento'
      AND object_id = OBJECT_ID(N'Audit.CasoValidacionAuditoria')
)
BEGIN
    CREATE INDEX IX_CasoValidacionAuditoria_Movimiento
    ON Audit.CasoValidacionAuditoria (idSucursal, idMovimientoInv)
    INCLUDE (CodigoRegla, EstadoValidacion, Numero);
END
GO
