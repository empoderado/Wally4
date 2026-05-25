/*
    WallyAgent 4.0
    Script 00 - Crear base empresarial WallyBD.

    Este script solo crea la base WallyBD si no existe. No modifica StudioF.
*/

IF DB_ID(N'WallyBD') IS NULL
BEGIN
    PRINT 'Creando base de datos WallyBD...';
    EXEC(N'CREATE DATABASE WallyBD');
END
ELSE
BEGIN
    PRINT 'La base de datos WallyBD ya existe.';
END
GO

USE WallyBD;
GO

IF SCHEMA_ID(N'Audit') IS NULL
BEGIN
    EXEC(N'CREATE SCHEMA Audit');
END
GO
