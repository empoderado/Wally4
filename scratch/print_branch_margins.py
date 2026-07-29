import sys
sys.path.append('.')
from services import db
from modules.reportes import _load_executive_report

db.load_environment()
min_d, max_d = db.min_max_date()
report = _load_executive_report(min_d, max_d)
df = report["branch_kpis"]
print(df[["Sucursal", "VentaNetaQ", "MargenQ", "%Margen", "Semáforo"]])
