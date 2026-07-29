import sys
sys.path.append('.')
from services import db

try:
    df = db.read_sql("SELECT TOP 5 VentaNetaQ, CostoTotal, (VentaNetaQ - CostoTotal) as MargenCalc, CostoTotal/NULLIF(VentaNetaQ,0) as PorcCosto, (VentaNetaQ - CostoTotal)/NULLIF(VentaNetaQ,0) as PorcMargen FROM dbo.VwFacturaConImpuesto")
    print(df)
except Exception as e:
    print("Error:", e)
