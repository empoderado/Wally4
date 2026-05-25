/*
    WallyAgent 4.0
    Script 09a - Bitacora administrativa para refrescos Mirror.
*/

USE WallyBD;
GO

IF SCHEMA_ID(N'Admin') IS NULL
BEGIN
    EXEC(N'CREATE SCHEMA Admin');
END;
GO

IF OBJECT_ID(N'Admin.RefrescoMirrorLog', N'U') IS NULL
BEGIN
    CREATE TABLE Admin.RefrescoMirrorLog (
        IdRefresco bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_RefrescoMirrorLog PRIMARY KEY,
        FechaInicio datetime2(0) NOT NULL CONSTRAINT DF_RefrescoMirrorLog_FechaInicio DEFAULT (SYSDATETIME()),
        FechaFin datetime2(0) NULL,
        Estado varchar(30) NOT NULL CONSTRAINT DF_RefrescoMirrorLog_Estado DEFAULT ('iniciado'),
        EjecutadoPor sysname NOT NULL CONSTRAINT DF_RefrescoMirrorLog_EjecutadoPor DEFAULT (SUSER_SNAME()),
        HostName sysname NULL CONSTRAINT DF_RefrescoMirrorLog_HostName DEFAULT (HOST_NAME()),
        AppName nvarchar(128) NULL CONSTRAINT DF_RefrescoMirrorLog_AppName DEFAULT (APP_NAME()),
        MensajeError nvarchar(4000) NULL
    );
END;
GO

IF OBJECT_ID(N'Admin.RefrescoMirrorDetalle', N'U') IS NULL
BEGIN
    CREATE TABLE Admin.RefrescoMirrorDetalle (
        IdDetalle bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_RefrescoMirrorDetalle PRIMARY KEY,
        IdRefresco bigint NOT NULL,
        Tabla sysname NOT NULL,
        FechaInicio datetime2(0) NOT NULL CONSTRAINT DF_RefrescoMirrorDetalle_FechaInicio DEFAULT (SYSDATETIME()),
        FechaFin datetime2(0) NULL,
        Estado varchar(30) NOT NULL CONSTRAINT DF_RefrescoMirrorDetalle_Estado DEFAULT ('iniciado'),
        FilasAntes bigint NULL,
        FilasFuente bigint NULL,
        FilasInsertadas bigint NULL,
        FilasFinal bigint NULL,
        MensajeError nvarchar(4000) NULL,
        CONSTRAINT FK_RefrescoMirrorDetalle_Log
            FOREIGN KEY (IdRefresco) REFERENCES Admin.RefrescoMirrorLog(IdRefresco)
    );
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = N'IX_RefrescoMirrorDetalle_IdRefresco'
      AND object_id = OBJECT_ID(N'Admin.RefrescoMirrorDetalle')
)
BEGIN
    CREATE INDEX IX_RefrescoMirrorDetalle_IdRefresco
    ON Admin.RefrescoMirrorDetalle (IdRefresco, Tabla);
END;
GO

SELECT TOP (20)
    IdRefresco,
    FechaInicio,
    FechaFin,
    Estado,
    EjecutadoPor,
    MensajeError
FROM Admin.RefrescoMirrorLog
ORDER BY IdRefresco DESC;
GO
