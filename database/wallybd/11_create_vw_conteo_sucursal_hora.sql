/*
    Wally4 - Conteo de facturas por sucursal y hora.

    Salida:
    - Timestamp: inicio de la hora con el formato solicitado por la API.
    - idSucursal: identificador de StudioF.
    - Sucursal: nombre de la sucursal.
    - TicketCount: facturas FV distintas generadas dentro de la hora.

    La vista genera tambien las combinaciones hora-sucursal sin ventas,
    asignando TicketCount = 0.
*/

USE WallyBD;
GO

CREATE OR ALTER VIEW dbo.VwConteoSucursalHora
AS
WITH
E1(N) AS
(
    SELECT N
    FROM (VALUES
        (0),(1),(2),(3),(4),(5),(6),(7),(8),(9)
    ) AS X(N)
),
E2(N) AS
(
    SELECT 1
    FROM E1 AS A
    CROSS JOIN E1 AS B
),
E4(N) AS
(
    SELECT 1
    FROM E2 AS A
    CROSS JOIN E2 AS B
),
E6(N) AS
(
    SELECT 1
    FROM E4 AS A
    CROSS JOIN E2 AS B
),
Numeros(N) AS
(
    SELECT ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1
    FROM E6
),
Limites AS
(
    SELECT
        DATEADD(HOUR, DATEDIFF(HOUR, 0, MIN(Fecha)), 0) AS HoraInicial,
        DATEADD(HOUR, DATEDIFF(HOUR, 0, GETDATE()), 0) AS HoraFinal
    FROM dbo.VwFacturaConImpuesto
    WHERE Trn = 'FV'
),
Horas AS
(
    SELECT DATEADD(HOUR, N.N, L.HoraInicial) AS HoraInicio
    FROM Numeros AS N
    CROSS JOIN Limites AS L
    WHERE N.N <= DATEDIFF(HOUR, L.HoraInicial, L.HoraFinal)
),
Sucursales AS
(
    SELECT
        S.idSucursal,
        S.Descripcion AS Sucursal
    FROM Mirror.Sucursal AS S
    WHERE EXISTS
    (
        SELECT 1
        FROM dbo.VwFacturaConImpuesto AS V
        WHERE V.Trn = 'FV'
          AND LTRIM(RTRIM(V.Sucursal)) COLLATE DATABASE_DEFAULT =
              LTRIM(RTRIM(S.Descripcion)) COLLATE DATABASE_DEFAULT
    )
),
FacturasPorHora AS
(
    SELECT
        DATEADD(HOUR, DATEDIFF(HOUR, 0, V.Fecha), 0) AS HoraInicio,
        V.Sucursal,
        COUNT(DISTINCT V.Numero) AS TicketCount
    FROM dbo.VwFacturaConImpuesto AS V
    WHERE V.Trn = 'FV'
    GROUP BY
        DATEADD(HOUR, DATEDIFF(HOUR, 0, V.Fecha), 0),
        V.Sucursal
)
SELECT
    H.HoraInicio AS HoraInicio,
    CONVERT(char(19), DATEADD(HOUR, 6, H.HoraInicio), 120) + '.0000000 UTC' AS [Timestamp],
    S.idSucursal,
    S.Sucursal,
    CAST(ISNULL(F.TicketCount, 0) AS int) AS TicketCount
FROM Horas AS H
CROSS JOIN Sucursales AS S
LEFT JOIN FacturasPorHora AS F
    ON F.HoraInicio = H.HoraInicio
   AND LTRIM(RTRIM(F.Sucursal)) COLLATE DATABASE_DEFAULT =
       LTRIM(RTRIM(S.Sucursal)) COLLATE DATABASE_DEFAULT;
GO

SELECT TOP (100)
    [Timestamp],
    idSucursal,
    Sucursal,
    TicketCount
FROM dbo.VwConteoSucursalHora
ORDER BY [Timestamp] DESC, idSucursal;
GO
