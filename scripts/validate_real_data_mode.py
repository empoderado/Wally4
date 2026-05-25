from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from services import db


def main() -> int:
    print("Validacion modo datos WallyAgent")
    print("===============================")
    print(f"APP_ENV={db.app_environment()}")
    print(f"USE_MOCK_DATA solicitado={'si' if db.mock_data_requested() else 'no'}")
    print(f"USE_MOCK_DATA efectivo={'si' if db.use_mock_data() else 'no'}")
    print(f"Origen={db.data_source_label()}")
    if db.app_environment() == "production" and db.use_mock_data():
        print("[ERROR] Produccion no puede ejecutar datos simulados.")
        return 1
    if db.app_environment() == "production" and db.data_source_label() != "SQL Server real":
        print("[ERROR] Produccion no esta configurada como SQL Server real.")
        return 1
    print("[OK] Modo de datos valido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
