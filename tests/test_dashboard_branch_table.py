from __future__ import annotations

import pandas as pd

from modules.dashboard_wally import _render_branch_table


def _row(branch: str, margin_pct: float) -> dict[str, object]:
    venta = 1000.0
    return {
        "Ranking": 1,
        "Sucursal": branch,
        "Unidades": 10,
        "VentaNetaQ": venta,
        "Facturas": 5,
        "Upt": 2.0,
        "FactProm": 200.0,
        "VrPromedioUnidad": 100.0,
        "MargenQ": venta * margin_pct,
        "%Margen": margin_pct,
        "DescuentoQ": 100.0,
        "%Desc": 0.10,
        "%VentaSuc": 0.50,
        "SemÃ¡foro": "Rojo" if margin_pct < 0.55 else "Amarillo",
    }


def test_branch_table_highlights_only_margins_below_54_percent() -> None:
    html = _render_branch_table(pd.DataFrame([_row("BAJO", 0.5399), _row("LIMITE", 0.54)]))

    low_cell = "<td class='wally-margin-column wally-margin-low'>53,99%</td>"
    threshold_cell = "<td class='wally-margin-column'>54,00%</td>"

    assert low_cell in html
    assert threshold_cell in html


def test_branch_table_renders_grouped_headers_and_total() -> None:
    html = _render_branch_table(pd.DataFrame([_row("CENTRAL", 0.60)]))

    assert "<th class='wally-group' colspan='3'>Ventas</th>" in html
    assert "<th class='wally-group wally-margin-group' colspan='2'>Margen</th>" in html
    assert "<tr class='wally-total'>" in html
    assert "<td class='wally-branch-name'>Total</td>" in html
