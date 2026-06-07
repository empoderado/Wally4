from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import pandas as pd

from agents.intent_router import detect_intent
from agents.kpi_agent import sales_by_seller
from agents.sql_agent import parse_query_context
from orchestration.maria_orchestrator import _seller_product_filters


class MariaSellerRankingTests(unittest.TestCase):
    def test_worst_advisor_is_detected_without_sales_word(self) -> None:
        self.assertEqual(detect_intent("Cual es la peor asesora del mes?"), "sales_by_seller")
        self.assertEqual(detect_intent("Que vendedora vendio menos hoy?"), "sales_by_seller")

    def test_extracts_limit_for_worst_advisors(self) -> None:
        self.assertEqual(parse_query_context("Dame las 3 peores asesoras").limit, 3)

    @patch("agents.kpi_agent.db.read_sql")
    def test_worst_advisor_is_sorted_by_lowest_net_sales(self, read_sql: Mock) -> None:
        read_sql.return_value = pd.DataFrame(
            [
                {
                    "Sucursal": "OAKLAND",
                    "Vendedor": "ASESORA ALTA",
                    "VentaNetaQ": 1000,
                    "Unidades": 10,
                    "Facturas": 5,
                    "MargenQ": 500,
                },
                {
                    "Sucursal": "MAJADAS",
                    "Vendedor": "ASESORA BAJA",
                    "VentaNetaQ": 100,
                    "Unidades": 1,
                    "Facturas": 1,
                    "MargenQ": 40,
                },
            ]
        )

        result = sales_by_seller(
            "2026-06-01",
            "2026-06-06",
            "mes actual",
            limit=1,
            ascending=True,
        )

        self.assertIn("ASESORA BAJA", result.answer)
        self.assertNotIn("ASESORA ALTA", result.answer)
        self.assertIn("Criterio: ordenadas por menor venta neta", result.answer)
        self.assertIn("MAJADAS", result.answer)

    @patch("agents.kpi_agent.db.read_sql")
    def test_jeans_ranking_filters_line_and_orders_by_units(self, read_sql: Mock) -> None:
        read_sql.return_value = pd.DataFrame(
            [
                {
                    "Sucursal": "OAKLAND",
                    "Vendedor": "ASESORA MAYOR VENTA",
                    "VentaNetaQ": 5000,
                    "Unidades": 4,
                    "Facturas": 3,
                    "MargenQ": 2500,
                },
                {
                    "Sucursal": "MAJADAS",
                    "Vendedor": "ASESORA MAS UNIDADES",
                    "VentaNetaQ": 4000,
                    "Unidades": 12,
                    "Facturas": 5,
                    "MargenQ": 2000,
                },
            ]
        )

        result = sales_by_seller(
            "2026-06-01",
            "2026-06-06",
            "mes actual",
            limit=1,
            product_filters=[("Linea", "JEAN")],
            product_label="Jean",
            order_by="units",
        )

        query, params = read_sql.call_args.args
        self.assertIn("CAST(Linea AS varchar(250))", query)
        self.assertEqual(params[-1], "JEAN")
        self.assertIn("ASESORA MAS UNIDADES", result.answer)
        self.assertNotIn("ASESORA MAYOR VENTA", result.answer)
        self.assertIn("mayor cantidad de unidades de Jean", result.answer)

    def test_explicit_merchan_takes_priority_over_bolso_word(self) -> None:
        filters, label = _seller_product_filters(
            "top 10 vendedoras que venden bolso merchan o linea merchan"
        )

        self.assertIn(("Linea", "MERCHAN"), filters)
        self.assertIn(("Descripcion3Tabla4", "MERCHAN"), filters)
        self.assertNotIn(("Linea", "BOLSO%"), filters)
        self.assertNotIn(("DescripTipoPrenda", "BOLSOS"), filters)
        self.assertEqual(label, "Merchan")

    @patch("agents.kpi_agent.db.read_sql")
    def test_bolso_merchan_ranking_uses_or_filters(self, read_sql: Mock) -> None:
        read_sql.return_value = pd.DataFrame(
            [
                {
                    "Sucursal": "OAKLAND",
                    "Vendedor": "ASESORA BOLSOS",
                    "VentaNetaQ": 1500,
                    "Unidades": 5,
                    "Facturas": 4,
                    "MargenQ": 800,
                }
            ]
        )

        filters, label = _seller_product_filters("bolso o linea merchan")
        result = sales_by_seller(
            "2026-06-01",
            "2026-06-06",
            "mes actual",
            product_filters=filters,
            product_label=label,
        )

        query, params = read_sql.call_args.args
        self.assertIn(" OR ", query)
        self.assertIn("CAST(Linea AS varchar(250))", query)
        self.assertIn("CAST(DescripTipoPrenda AS varchar(250))", query)
        self.assertIn("CAST(Descripcion3Tabla4 AS varchar(250))", query)
        self.assertIn("MERCHAN", params)
        self.assertNotIn("BOLSO%", params)
        self.assertIn("Merchan", result.answer)


if __name__ == "__main__":
    unittest.main()
