import sys
sys.path.append('.')
from services import db
from modules.reportes import _load_executive_report

db.load_environment()
min_d, max_d = db.min_max_date()
report = _load_executive_report(min_d, max_d)
df = report["branch_kpis"]
df["%Margen_VentaNeta"] = df["MargenQ"] / df["VentaNetaQ"]
df["%Margen_VentaBruta"] = df["MargenQ"] / df["VentaBruta"]
print(df[["Sucursal", "VentaNetaQ", "VentaBruta", "MargenQ", "%Margen", "%Margen_VentaNeta", "%Margen_VentaBruta"]])
