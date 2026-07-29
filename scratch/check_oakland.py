import sys
sys.path.append('.')
from services import db

db.load_environment()
df = db.read_sql("SELECT SUM(VentaNetaQ) as VentaNetaQ, SUM(CostoTotal) as CostoTotal, SUM(VentaNetaQ) - SUM(CostoTotal) as MargenCalc, SUM(MargenQ) as MargenQ FROM dbo.VwFacturaConImpuesto WHERE Sucursal='OAKLAND'")
print(df)
