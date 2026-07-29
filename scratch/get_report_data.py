import sys
sys.path.append('.')
from datetime import date
from services import db
from modules.reportes import _load_executive_report

db.load_environment()
# Find min/max date
min_d, max_d = db.min_max_date()
print(f"Date range: {min_d} to {max_d}")

# Let's load the executive report
report = _load_executive_report(min_d, max_d)
print("\nKPIs summary:")
print(report["summary"])

print("\nBranch KPIs:")
print(report["branch_kpis"])
