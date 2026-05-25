/*
    WallyAgent 4.0
    Script 01 - Crear vistas espejo en WallyBD.

    Objetivo:
    - Mantener StudioF intacta.
    - Permitir que WallyAgent V4 apunte a WallyBD y siga usando nombres dbo.*
      ya autorizados en la aplicacion.

    Nota:
    Estas vistas son el contrato publico de la app y leen tablas materializadas
    Mirror.* dentro de WallyBD. La alimentacion desde StudioF se realiza por
    scripts administrativos separados.
*/

USE WallyBD;
GO

CREATE OR ALTER VIEW dbo.VwFacturaConImpuesto
AS
    SELECT *
    FROM Mirror.FacturaConImpuesto;
GO

CREATE OR ALTER VIEW dbo.VwExistencia
AS
    SELECT *
    FROM Mirror.Existencia;
GO

CREATE OR ALTER VIEW dbo.VwEntradasInventario
AS
    SELECT *
    FROM Mirror.EntradasInventario;
GO

CREATE OR ALTER VIEW dbo.VwClienteResumenCRM
AS
    SELECT *
    FROM Mirror.ClienteResumenCRM;
GO
