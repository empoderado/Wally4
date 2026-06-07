from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import pandas as pd

from agents.intent_router import detect_intent
from agents.kpi_agent import sales_by_branch
from orchestration.maria_orchestrator import _seller_product_filters


class MariaProductByBranchTests(unittest.TestCase):
    def test_merchan_quantity_routes_to_sales_by_branch(self) -> None:
        self.assertEqual(
            detect_intent("Cuantos merchan se han vendido este mes?"),
            "sales_by_branch",
        )
        self.assertEqual(
            detect_intent("Dame la venta de Linea Merchant de este mes"),
            "sales_by_branch",
        )

    def test_audio_alias_merchant_maps_to_merchan(self) -> None:
        filters, label = _seller_product_filters(
            "dame la venta de linea merchant de este mes"
        )

        self.assertEqual(label, "Merchan")
        self.assertIn(("Linea", "MERCHAN"), filters)
        self.assertIn(("Descripcion3Tabla4", "MERCHAN"), filters)

    @patch("agents.kpi_agent.db.read_sql")
    def test_merchan_units_are_grouped_and_ranked_by_branch(self, read_sql: Mock) -> None:
        read_sql.return_value = pd.DataFrame(
            [
                {
                    "Sucursal": "OAKLAND",
                    "VentaNetaQ": 198,
                    "Unidades": 2,
                    "Facturas": 2,
                    "CostoTotal": 231,
                    "MargenQ": -33,
                },
                {
                    "Sucursal": "CHIQUIMULA",
                    "VentaNetaQ": 1697,
                    "Unidades": 9,
                    "Facturas": 9,
                    "CostoTotal": 1171,
                    "MargenQ": 526,
                },
            ]
        )
        filters, label = _seller_product_filters("cuantos merchan se han vendido")

        result = sales_by_branch(
            "2026-06-01",
            "2026-06-06",
            "mes actual",
            product_filters=filters,
            product_label=label,
            order_by="units",
        )

        query, params = read_sql.call_args.args
        self.assertIn("GROUP BY Sucursal", query)
        self.assertIn("CAST(Linea AS varchar(250))", query)
        self.assertIn("MERCHAN", params)
        self.assertLess(result.answer.index("CHIQUIMULA"), result.answer.index("OAKLAND"))
        self.assertIn("Unidades vendidas de Merchan por sucursal", result.answer)
        self.assertIn("Unid: 9", result.answer)


if __name__ == "__main__":
    unittest.main()
