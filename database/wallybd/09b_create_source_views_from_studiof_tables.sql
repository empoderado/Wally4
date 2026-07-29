/*
    WallyAgent 4.0
    Script 09b - Vistas Source en WallyBD desde tablas base de StudioF.

    Objetivo:
    - El proceso administrativo de refresco no depende de vistas en StudioF.
    - Si se eliminan StudioF.dbo.VwFacturaConImpuesto, VwExistencia,
      VwEntradasInventario o VwClienteResumenCRM, WallyBD puede seguir
      alimentando Mirror.* desde tablas base de StudioF.
*/

USE WallyBD;
GO

IF SCHEMA_ID(N'Source') IS NULL
BEGIN
    EXEC(N'CREATE SCHEMA Source');
END;
GO

CREATE OR ALTER VIEW Source.VwFacturaConImpuesto
AS
WITH Base AS
(
    SELECT
        mi.Fecha,
        CAST(mi.Fecha AS date) AS FechaDocumento,
        CAST(mi.Fecha AS time(0)) AS HoraDocumento,
        s.Descripcion AS Sucursal,
        ti.Sigla AS Trn,
        mi.Numero,
        t1.Descripcion AS Referencia,
        a.Referencia AS CodBarras,
        a.Codigo AS NombreTallaColor,
        t2.Descripcion AS Coleccion,
        t2.Description AS Coleccion_EN,
        t3.Descripcion AS CodDescripTipoPrenda,
        t3.Description AS DescripTipoPrenda,
        t4.Descripcion AS CodDescLinea,
        t4.Description AS Linea,
        t4.Descripcion3 AS Descripcion3Tabla4,
        t5.Descripcion AS CodDescSubLinea,
        t5.Description AS DescSubLinea,
        t6.Descripcion AS CodColor,
        t6.Description AS Sublinea_EN,
        t7.Descripcion AS CodEmbarque,
        t7.Description AS CodEmbarqueAbreviado,
        t8.Descripcion AS EMB,
        t8.Description AS EMB_EN,
        t9.Descripcion AS Talla,
        t9.Description AS Tabla9_Description,
        t10.Descripcion AS ColorSF,
        t10.Description AS Color,
        a.Descripcion AS DescripcionArticulo,
        CASE WHEN ti.Sigla IN ('NC', 'NCC') THEN ABS(mia.Cantidad) * -1 ELSE ABS(mia.Cantidad) END AS Unidades,
        ABS(mia.Costo) AS Costo,
        ABS(mia.Precio) AS PrecioUnit,
        ISNULL(mia.Descuento, 0) AS Descuento,
        CASE
            WHEN ABS(ISNULL(mia.Descuento, 0)) > 1 THEN ABS(ISNULL(mia.Descuento, 0)) / 100.0
            ELSE ABS(ISNULL(mia.Descuento, 0))
        END AS DescuentoPctBase,
        CASE WHEN ti.Sigla IN ('NC', 'NCC') THEN ABS(ISNULL(mia.Impuesto, 0)) * -1 ELSE ABS(ISNULL(mia.Impuesto, 0)) END AS Impuesto,
        mi.idEmpleadoVendedor AS IdVendedor,
        LTRIM(RTRIM(ISNULL(ev.Nombres, '') + ' ' + ISNULL(ev.Apellidos, ''))) AS Vendedor,
        c.IDT AS Cuenta,
        c.Nombre AS Cliente,
        ISNULL(cd.Direccion, c.Direccion) AS Direccion,
        ISNULL(cd.eMail, c.eMail) AS eMail,
        c.FechaNacimiento AS [Fecha Nacimiento],
        ISNULL(cd.Telefono, c.Telefono) AS Telefono,
        ISNULL(cd.Telefono, c.Telefono) AS Celular
    FROM StudioF.dbo.MovimientoInv AS mi
    INNER JOIN StudioF.dbo.MovimientoInvArticulo AS mia
        ON mi.idSucursal = mia.idSucursal
       AND mi.idMovimientoInv = mia.idMovimientoInv
    INNER JOIN StudioF.dbo.Sucursal AS s
        ON mi.idSucursal = s.idSucursal
    INNER JOIN StudioF.dbo.TransaccionInv AS ti
        ON mi.idTransaccionInv = ti.idTransaccionInv
    INNER JOIN StudioF.dbo.Articulo AS a
        ON mia.idArticulo = a.idArticulo
    LEFT JOIN StudioF.dbo.Tabla1 AS t1 ON a.IdTabla1 = t1.IdTabla1
    LEFT JOIN StudioF.dbo.Tabla2 AS t2 ON a.IdTabla2 = t2.IdTabla2
    LEFT JOIN StudioF.dbo.Tabla3 AS t3 ON a.IdTabla3 = t3.IdTabla3
    LEFT JOIN StudioF.dbo.Tabla4 AS t4 ON a.IdTabla4 = t4.IdTabla4
    LEFT JOIN StudioF.dbo.Tabla5 AS t5 ON a.IdTabla5 = t5.IdTabla5
    LEFT JOIN StudioF.dbo.Tabla6 AS t6 ON a.IdTabla6 = t6.IdTabla6
    LEFT JOIN StudioF.dbo.Tabla7 AS t7 ON a.IdTabla7 = t7.IdTabla7
    LEFT JOIN StudioF.dbo.Tabla8 AS t8 ON a.IdTabla8 = t8.IdTabla8
    LEFT JOIN StudioF.dbo.Tabla9 AS t9 ON a.IdTabla9 = t9.IdTabla9
    LEFT JOIN StudioF.dbo.Tabla10 AS t10 ON a.IdTabla10 = t10.IdTabla10
    LEFT JOIN StudioF.dbo.Cliente AS c ON mi.idCliente = c.idCliente
    LEFT JOIN StudioF.dbo.ClienteDireccion AS cd ON mi.idClienteDireccion = cd.idClienteDireccion
    LEFT JOIN StudioF.dbo.Empleado AS ev ON mi.idEmpleadoVendedor = ev.idEmpleado
    WHERE mi.FlagAnulado = 0
      AND ti.FlagAfectaCtaCliente = 1
      AND ti.Sigla IN ('FV', 'NC', 'NCC')
),
Calc AS
(
    SELECT
        *,
        CASE WHEN DescuentoPctBase > 1 THEN 1 ELSE DescuentoPctBase END AS DescuentoPct
    FROM Base
)
SELECT
    Sucursal,
    Fecha,
    FechaDocumento,
    HoraDocumento,
    Trn,
    Numero,
    Referencia,
    CodBarras,
    NombreTallaColor,
    Coleccion,
    Coleccion_EN,
    CodDescripTipoPrenda,
    DescripTipoPrenda,
    CodDescLinea,
    Linea,
    Descripcion3Tabla4,
    CodDescSubLinea,
    DescSubLinea,
    CodColor,
    Sublinea_EN,
    CodEmbarque,
    CodEmbarqueAbreviado,
    EMB,
    EMB_EN,
    Talla,
    Tabla9_Description,
    ColorSF,
    Color,
    DescripcionArticulo,
    Unidades,
    Costo,
    CAST(ROUND(Costo * Unidades, 2) AS decimal(18, 2)) AS CostoTotal,
    PrecioUnit,
    CAST(ROUND(PrecioUnit * Unidades, 2) AS decimal(18, 2)) AS VentaBruta,
    Descuento,
    DescuentoPct,
    CAST(ROUND(PrecioUnit * Unidades * DescuentoPct, 2) AS decimal(18, 2)) AS DescuentoValor,
    Impuesto,
    CAST(ROUND(PrecioUnit * Unidades - PrecioUnit * Unidades * DescuentoPct, 2) AS decimal(18, 2)) AS VentaNetaQ,
    IdVendedor,
    Vendedor,
    Cuenta,
    Cliente,
    Direccion,
    eMail,
    [Fecha Nacimiento],
    Telefono,
    Celular
FROM Calc;
GO

CREATE OR ALTER VIEW Source.VwExistencia
AS
WITH Base AS
(
    SELECT
        s.idSucursal,
        s.Descripcion AS Sucursal,
        a.idArticulo,
        t1.Descripcion AS Referencia,
        a.Referencia AS CodBarras,
        a.Codigo AS NombreTallaColor,
        t2.Descripcion AS Coleccion,
        t2.Description AS Coleccion_EN,
        t3.Descripcion AS CodDescripTipoPrenda,
        t3.Description AS DescripTipoPrenda,
        t4.Descripcion AS CodDescLinea,
        t4.Description AS Linea,
        t4.Descripcion3 AS Descripcion3Linea,
        t5.Descripcion AS CodDescSubLinea,
        t5.Description AS DescSubLinea,
        t6.Descripcion AS CodColor,
        t6.Description AS Sublinea_EN,
        t7.Descripcion AS CodEmbarque,
        t7.Description AS CodEmbarqueAbreviado,
        t9.Descripcion AS Talla,
        t9.Description AS Tabla9_Description,
        t10.Descripcion AS ColorSF,
        t10.Description AS Color,
        a.Descripcion AS DescripcionArticulo,
        CAST(ars.Existencia AS int) AS ExistenciaFisica,
        CAST(ars.Existencia - ISNULL(ars.FijoPorEgresar, 0) AS int) AS ExistenciaDisponible,
        CAST(a.FechaIngreso AS date) AS FechaEntradaReferencia,
        CAST(MIN(a.FechaIngreso) OVER (PARTITION BY t7.IdTabla7) AS date) AS FechaEntradaEmbarque
    FROM StudioF.dbo.ArticuloSucursal AS ars
    INNER JOIN StudioF.dbo.Articulo AS a ON ars.idArticulo = a.idArticulo
    INNER JOIN StudioF.dbo.Sucursal AS s ON ars.idSucursal = s.idSucursal
    LEFT JOIN StudioF.dbo.Tabla1 AS t1 ON a.IdTabla1 = t1.IdTabla1
    LEFT JOIN StudioF.dbo.Tabla2 AS t2 ON a.IdTabla2 = t2.IdTabla2
    LEFT JOIN StudioF.dbo.Tabla3 AS t3 ON a.IdTabla3 = t3.IdTabla3
    LEFT JOIN StudioF.dbo.Tabla4 AS t4 ON a.IdTabla4 = t4.IdTabla4
    LEFT JOIN StudioF.dbo.Tabla5 AS t5 ON a.IdTabla5 = t5.IdTabla5
    LEFT JOIN StudioF.dbo.Tabla6 AS t6 ON a.IdTabla6 = t6.IdTabla6
    LEFT JOIN StudioF.dbo.Tabla7 AS t7 ON a.IdTabla7 = t7.IdTabla7
    LEFT JOIN StudioF.dbo.Tabla9 AS t9 ON a.IdTabla9 = t9.IdTabla9
    LEFT JOIN StudioF.dbo.Tabla10 AS t10 ON a.IdTabla10 = t10.IdTabla10
    WHERE a.FlagActivo = 1
      AND a.FlagExistencia = 1
      AND NOT (ars.Existencia = 0 AND (ars.Existencia - ISNULL(ars.FijoPorEgresar, 0)) = 0)
)
SELECT
    Sucursal,
    Referencia,
    CodBarras,
    NombreTallaColor,
    Coleccion,
    Coleccion_EN,
    CodDescripTipoPrenda,
    DescripTipoPrenda,
    CodDescLinea,
    Linea,
    Descripcion3Linea,
    CodDescSubLinea,
    DescSubLinea,
    CodColor,
    Sublinea_EN,
    CodEmbarque,
    CodEmbarqueAbreviado,
    Talla,
    Tabla9_Description,
    ColorSF,
    Color,
    DescripcionArticulo,
    ExistenciaFisica,
    ExistenciaDisponible,
    FechaEntradaReferencia,
    FechaEntradaEmbarque,
    CAST(DATEDIFF(DAY, FechaEntradaEmbarque, CAST(GETDATE() AS date)) AS int) AS TVida,
    idArticulo,
    idSucursal
FROM Base;
GO

CREATE OR ALTER VIEW Source.VwEntradasInventario
AS
WITH Base AS
(
    SELECT
        CAST(mi.Fecha AS date) AS FechaEntrada,
        CAST(CAST(mi.Fecha AS date) AS datetime) AS FechaHoraEntrada,
        s.idSucursal,
        s.Descripcion AS Sucursal,
        a.idArticulo,
        a.Codigo AS NombreTallaColor,
        t1.Descripcion AS Referencia,
        a.Referencia AS CodBarras,
        a.Descripcion AS DescripcionArticulo,
        t7.Descripcion AS CodEmbarque,
        t7.Description AS CodEmbarqueAbreviado,
        t4.Description AS Linea,
        t3.Description AS DescripTipoPrenda,
        t9.Descripcion AS Talla,
        t10.Description AS Color,
        ti.Sigla AS SiglaTransaccion,
        ti.Descripcion AS Transaccion,
        CAST(mia.Cantidad AS int) AS UnidadesEntrada
    FROM StudioF.dbo.MovimientoInv AS mi
    INNER JOIN StudioF.dbo.MovimientoInvArticulo AS mia
        ON mi.idSucursal = mia.idSucursal
       AND mi.idMovimientoInv = mia.idMovimientoInv
    INNER JOIN StudioF.dbo.TransaccionInv AS ti ON mi.idTransaccionInv = ti.idTransaccionInv
    INNER JOIN StudioF.dbo.Sucursal AS s ON mi.idSucursal = s.idSucursal
    INNER JOIN StudioF.dbo.Articulo AS a ON mia.idArticulo = a.idArticulo
    LEFT JOIN StudioF.dbo.Tabla1 AS t1 ON a.IdTabla1 = t1.IdTabla1
    LEFT JOIN StudioF.dbo.Tabla3 AS t3 ON a.IdTabla3 = t3.IdTabla3
    LEFT JOIN StudioF.dbo.Tabla4 AS t4 ON a.IdTabla4 = t4.IdTabla4
    LEFT JOIN StudioF.dbo.Tabla7 AS t7 ON a.IdTabla7 = t7.IdTabla7
    LEFT JOIN StudioF.dbo.Tabla9 AS t9 ON a.IdTabla9 = t9.IdTabla9
    LEFT JOIN StudioF.dbo.Tabla10 AS t10 ON a.IdTabla10 = t10.IdTabla10
    WHERE mi.FlagAnulado = 0
      AND ti.FlagAfectaInventario = 1
      AND mia.Cantidad > 0
)
SELECT
    FechaEntrada,
    FechaHoraEntrada,
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
    SUM(UnidadesEntrada) AS UnidadesEntrada
FROM Base
WHERE SiglaTransaccion = 'DDP'
GROUP BY
    FechaEntrada,
    FechaHoraEntrada,
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
    Transaccion;
GO

CREATE OR ALTER VIEW Source.VwClienteResumenCRM
AS
WITH VentasFV AS
(
    SELECT
        CAST(v.Cuenta AS varchar(50)) COLLATE DATABASE_DEFAULT AS NitDpi,
        LTRIM(RTRIM(CAST(v.Cliente AS varchar(250)))) COLLATE DATABASE_DEFAULT AS Cliente,
        NULLIF(LTRIM(RTRIM(CAST(v.Telefono AS varchar(100)))), '') AS Telefono,
        NULLIF(LTRIM(RTRIM(CAST(v.Celular AS varchar(100)))), '') AS Celular,
        NULLIF(LTRIM(RTRIM(CAST(v.eMail AS varchar(250)))), '') AS Email,
        CAST(c.FechaNacimiento AS date) AS FechaCumpleanos,
        NULLIF(LTRIM(RTRIM(CAST(c.Direccion AS varchar(MAX)))), '') AS Direccion,
        NULLIF(LTRIM(RTRIM(CAST(d.Descripcion AS varchar(100)))), '') AS Departamento,
        NULLIF(LTRIM(RTRIM(CAST(m.Descripcion AS varchar(100)))), '') AS Ciudad,
        CAST(v.FechaDocumento AS date) AS FechaDocumento,
        v.Sucursal COLLATE DATABASE_DEFAULT AS Sucursal,
        v.Trn COLLATE DATABASE_DEFAULT AS Trn,
        CAST(v.Numero AS varchar(50)) COLLATE DATABASE_DEFAULT AS Numero,
        CONCAT(
            CAST(v.Sucursal AS varchar(100)) COLLATE DATABASE_DEFAULT,
            '|',
            CAST(v.Trn AS varchar(20)) COLLATE DATABASE_DEFAULT,
            '|',
            CAST(v.Numero AS varchar(50)) COLLATE DATABASE_DEFAULT
        ) AS FacturaKey,
        v.IdVendedor,
        v.Vendedor COLLATE DATABASE_DEFAULT AS Vendedor,
        ISNULL(v.Unidades, 0) AS Unidades,
        ISNULL(v.VentaNetaQ, 0) AS VentaNetaQ,
        ISNULL(v.DescuentoPct, 0) AS DescuentoPct,
        v.Linea COLLATE DATABASE_DEFAULT AS Linea,
        v.DescripTipoPrenda COLLATE DATABASE_DEFAULT AS DescripTipoPrenda,
        v.Talla COLLATE DATABASE_DEFAULT AS Talla
    FROM Mirror.FacturaConImpuesto AS v
    LEFT JOIN StudioF.dbo.Cliente AS c
        ON CAST(v.Cuenta AS varchar(50)) COLLATE DATABASE_DEFAULT = CAST(c.IDT AS varchar(50)) COLLATE DATABASE_DEFAULT
    LEFT JOIN StudioF.dbo.Departamento AS d ON c.idDepartamento = d.idDepartamento
    LEFT JOIN StudioF.dbo.Municipio AS m
        ON c.idMunicipio = m.idMunicipio
       AND c.idDepartamento = m.idDepartamento
    WHERE v.Trn = 'FV'
      AND v.Cuenta IS NOT NULL
      AND LTRIM(RTRIM(CAST(v.Cuenta AS varchar(50)))) <> ''
      AND v.Cliente IS NOT NULL
      AND UPPER(LTRIM(RTRIM(CAST(v.Cliente AS varchar(250))))) COLLATE DATABASE_DEFAULT NOT IN
      (
          'CONSUMIDOR FINAL',
          'CLIENTE GENERAL',
          'SIN NOMBRE',
          'CF',
          'C/F'
      )
),
ClientesConTelefono AS
(
    SELECT *
    FROM VentasFV
    WHERE ISNULL(Telefono, '') <> ''
       OR ISNULL(Celular, '') <> ''
),
TotalesCliente AS
(
    SELECT
        NitDpi,
        MAX(Cliente) AS Cliente,
        MAX(Telefono) AS Telefono,
        MAX(Celular) AS Celular,
        MAX(Email) AS Email,
        MAX(FechaCumpleanos) AS FechaCumpleanos,
        MAX(Direccion) AS Direccion,
        MAX(Departamento) AS Departamento,
        MAX(Ciudad) AS Ciudad,
        COUNT(DISTINCT FacturaKey) AS FacturasTotales,
        SUM(Unidades) AS UnidadesTotales,
        SUM(VentaNetaQ) AS VentaNetaTotal,
        SUM(CASE WHEN DescuentoPct <= 0.20 THEN Unidades ELSE 0 END) AS UnidadesFullPrecio,
        SUM(CASE WHEN DescuentoPct > 0.20 THEN Unidades ELSE 0 END) AS UnidadesPromocion,
        SUM(CASE WHEN DescuentoPct <= 0.20 THEN VentaNetaQ ELSE 0 END) AS VentaFullPrecio,
        SUM(CASE WHEN DescuentoPct > 0.20 THEN VentaNetaQ ELSE 0 END) AS VentaPromocion,
        MAX(FechaDocumento) AS FechaUltimaCompra,
        CAST(ISNULL(SUM(CASE WHEN UPPER(Linea) = 'BLUSA' THEN Unidades ELSE 0 END), 0) AS int) AS Blusas,
        CAST(ISNULL(SUM(CASE WHEN UPPER(Linea) = 'JEAN' THEN Unidades ELSE 0 END), 0) AS int) AS Jeans,
        CAST(ISNULL(SUM(CASE WHEN UPPER(Linea) = 'VESTIDO' THEN Unidades ELSE 0 END), 0) AS int) AS Vestidos,
        CAST(ISNULL(SUM(CASE WHEN UPPER(Linea) = 'PANTALON' THEN Unidades ELSE 0 END), 0) AS int) AS Pantalones,
        CAST(ISNULL(SUM(CASE WHEN UPPER(Linea) NOT IN ('BLUSA', 'JEAN', 'VESTIDO', 'PANTALON') THEN Unidades ELSE 0 END), 0) AS int) AS Otros
    FROM ClientesConTelefono
    GROUP BY NitDpi
),
SucursalCliente AS
(
    SELECT
        NitDpi,
        Sucursal,
        COUNT(DISTINCT FacturaKey) AS FacturasSucursal,
        SUM(VentaNetaQ) AS VentaNetaSucursal,
        MAX(FechaDocumento) AS FechaUltimaCompraSucursal
    FROM ClientesConTelefono
    GROUP BY NitDpi, Sucursal
),
SucursalPreferida AS
(
    SELECT
        NitDpi,
        Sucursal AS SucursalPreferida,
        FacturasSucursal,
        VentaNetaSucursal,
        FechaUltimaCompraSucursal,
        ROW_NUMBER() OVER (
            PARTITION BY NitDpi
            ORDER BY FacturasSucursal DESC, VentaNetaSucursal DESC, FechaUltimaCompraSucursal DESC, Sucursal ASC
        ) AS rn
    FROM SucursalCliente
),
UltimaFactura AS
(
    SELECT
        NitDpi,
        Sucursal AS SucursalUltimaCompra,
        Numero AS NumeroUltimaFactura,
        IdVendedor AS IdVendedorUltimaFactura,
        Vendedor AS VendedorUltimaFactura,
        FechaDocumento AS FechaUltimaFactura,
        ROW_NUMBER() OVER (
            PARTITION BY NitDpi
            ORDER BY FechaDocumento DESC, Numero DESC
        ) AS rn
    FROM ClientesConTelefono
),
TallaFrecuenteBlusa AS
(
    SELECT
        CAST(v.Cuenta AS varchar(50)) COLLATE DATABASE_DEFAULT AS NitDpi,
        v.Talla AS TallaBlusa,
        ROW_NUMBER() OVER (
            PARTITION BY CAST(v.Cuenta AS varchar(50)) COLLATE DATABASE_DEFAULT
            ORDER BY SUM(v.Unidades) DESC, v.Talla ASC
        ) AS rn
    FROM Mirror.FacturaConImpuesto AS v
    WHERE v.Trn = 'FV'
      AND UPPER(v.Linea) = 'BLUSA'
      AND v.Talla IS NOT NULL 
      AND v.Talla <> ''
      AND v.Cuenta IS NOT NULL
      AND LTRIM(RTRIM(CAST(v.Cuenta AS varchar(50)))) <> ''
      AND v.Cliente IS NOT NULL
      AND UPPER(LTRIM(RTRIM(CAST(v.Cliente AS varchar(250))))) COLLATE DATABASE_DEFAULT NOT IN
      (
          'CONSUMIDOR FINAL',
          'CLIENTE GENERAL',
          'SIN NOMBRE',
          'CF',
          'C/F'
      )
    GROUP BY CAST(v.Cuenta AS varchar(50)) COLLATE DATABASE_DEFAULT, v.Talla
),
TallaFrecuenteJean AS
(
    SELECT
        CAST(v.Cuenta AS varchar(50)) COLLATE DATABASE_DEFAULT AS NitDpi,
        v.Talla AS TallaJean,
        ROW_NUMBER() OVER (
            PARTITION BY CAST(v.Cuenta AS varchar(50)) COLLATE DATABASE_DEFAULT
            ORDER BY SUM(v.Unidades) DESC, v.Talla ASC
        ) AS rn
    FROM Mirror.FacturaConImpuesto AS v
    WHERE v.Trn = 'FV'
      AND UPPER(v.Linea) = 'JEAN'
      AND v.Talla IS NOT NULL 
      AND v.Talla <> ''
      AND v.Cuenta IS NOT NULL
      AND LTRIM(RTRIM(CAST(v.Cuenta AS varchar(50)))) <> ''
      AND v.Cliente IS NOT NULL
      AND UPPER(LTRIM(RTRIM(CAST(v.Cliente AS varchar(250))))) COLLATE DATABASE_DEFAULT NOT IN
      (
          'CONSUMIDOR FINAL',
          'CLIENTE GENERAL',
          'SIN NOMBRE',
          'CF',
          'C/F'
      )
    GROUP BY CAST(v.Cuenta AS varchar(50)) COLLATE DATABASE_DEFAULT, v.Talla
),
TallaFrecuenteCalzado AS
(
    SELECT
        CAST(v.Cuenta AS varchar(50)) COLLATE DATABASE_DEFAULT AS NitDpi,
        v.Talla AS TallaCalzado,
        ROW_NUMBER() OVER (
            PARTITION BY CAST(v.Cuenta AS varchar(50)) COLLATE DATABASE_DEFAULT
            ORDER BY SUM(v.Unidades) DESC, v.Talla ASC
        ) AS rn
    FROM Mirror.FacturaConImpuesto AS v
    WHERE v.Trn = 'FV'
      AND UPPER(v.DescripTipoPrenda) = 'CALZADO'
      AND v.Talla IS NOT NULL 
      AND v.Talla <> ''
      AND v.Cuenta IS NOT NULL
      AND LTRIM(RTRIM(CAST(v.Cuenta AS varchar(50)))) <> ''
      AND v.Cliente IS NOT NULL
      AND UPPER(LTRIM(RTRIM(CAST(v.Cliente AS varchar(250))))) COLLATE DATABASE_DEFAULT NOT IN
      (
          'CONSUMIDOR FINAL',
          'CLIENTE GENERAL',
          'SIN NOMBRE',
          'CF',
          'C/F'
      )
    GROUP BY CAST(v.Cuenta AS varchar(50)) COLLATE DATABASE_DEFAULT, v.Talla
),
Resumen AS
(
    SELECT
        tc.NitDpi,
        tc.Cliente,
        tc.Telefono,
        tc.Celular,
        tc.Email,
        tc.FechaCumpleanos,
        tc.Direccion,
        tc.Departamento,
        tc.Ciudad,
        tc.FechaUltimaCompra,
        DATEDIFF(DAY, tc.FechaUltimaCompra, CAST(GETDATE() AS date)) AS DiasSinCompra,
        sp.SucursalPreferida,
        sp.FacturasSucursal AS FacturasSucursalPreferida,
        uf.SucursalUltimaCompra,
        uf.NumeroUltimaFactura,
        uf.IdVendedorUltimaFactura,
        uf.VendedorUltimaFactura,
        tc.FacturasTotales,
        tc.UnidadesTotales,
        tc.VentaNetaTotal,
        tc.UnidadesFullPrecio,
        tc.UnidadesPromocion,
        tc.VentaFullPrecio,
        tc.VentaPromocion,
        tc.Blusas,
        tc.Jeans,
        tc.Vestidos,
        tc.Pantalones,
        tc.Otros,
        tfb.TallaBlusa,
        tfj.TallaJean,
        tfc.TallaCalzado
    FROM TotalesCliente AS tc
    INNER JOIN SucursalPreferida AS sp ON tc.NitDpi = sp.NitDpi AND sp.rn = 1
    INNER JOIN UltimaFactura AS uf ON tc.NitDpi = uf.NitDpi AND uf.rn = 1
    LEFT JOIN TallaFrecuenteBlusa AS tfb ON tc.NitDpi = tfb.NitDpi AND tfb.rn = 1
    LEFT JOIN TallaFrecuenteJean AS tfj ON tc.NitDpi = tfj.NitDpi AND tfj.rn = 1
    LEFT JOIN TallaFrecuenteCalzado AS tfc ON tc.NitDpi = tfc.NitDpi AND tfc.rn = 1
)
SELECT
    ROW_NUMBER() OVER (ORDER BY DiasSinCompra DESC, VentaNetaTotal DESC, Cliente ASC) AS NumeroCliente,
    NitDpi,
    Cliente,
    Telefono,
    Celular,
    Email,
    FechaCumpleanos,
    Direccion,
    Departamento,
    Ciudad,
    FechaUltimaCompra,
    DiasSinCompra,
    CASE
        WHEN DiasSinCompra BETWEEN 1 AND 60 THEN '1 a 60 dias'
        WHEN DiasSinCompra BETWEEN 61 AND 120 THEN '61 a 120 dias'
        WHEN DiasSinCompra >= 121 THEN '121 dias en adelante'
        ELSE 'Compra reciente'
    END AS SegmentoSinCompra,
    SucursalPreferida,
    FacturasSucursalPreferida,
    SucursalUltimaCompra,
    NumeroUltimaFactura,
    IdVendedorUltimaFactura,
    VendedorUltimaFactura,
    FacturasTotales,
    UnidadesTotales,
    VentaNetaTotal,
    UnidadesFullPrecio,
    UnidadesPromocion,
    VentaFullPrecio,
    VentaPromocion,
    CASE WHEN UnidadesTotales = 0 THEN 0 ELSE CAST(UnidadesFullPrecio AS decimal(18, 4)) / NULLIF(UnidadesTotales, 0) END AS PorcentajeFullPrecio,
    CASE WHEN UnidadesTotales = 0 THEN 0 ELSE CAST(UnidadesPromocion AS decimal(18, 4)) / NULLIF(UnidadesTotales, 0) END AS PorcentajePromocion,
    Blusas,
    Jeans,
    Vestidos,
    Pantalones,
    Otros,
    TallaBlusa,
    TallaJean,
    TallaCalzado
FROM Resumen
WHERE DiasSinCompra >= 1;
GO
