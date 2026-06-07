from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from agents.kpi_agent import sales_summary
from memory.conversation_context import answer_from_context
from memory.conversation_context import contextualize_question
from memory.conversation_context import save_result_context
from services.local_store import init_store
from services.maria_ai import enhance_answer


class MariaConversationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_sqlite_path = os.environ.get("WALLY_AGENT_SQLITE_PATH")
        os.environ["WALLY_AGENT_SQLITE_PATH"] = str(Path(self.temp_dir.name) / "maria_test.sqlite")
        init_store()

    def tearDown(self) -> None:
        if self.previous_sqlite_path is None:
            os.environ.pop("WALLY_AGENT_SQLITE_PATH", None)
        else:
            os.environ["WALLY_AGENT_SQLITE_PATH"] = self.previous_sqlite_path
        self.temp_dir.cleanup()

    def test_follow_up_uses_ranked_branch_and_sales_domain(self) -> None:
        save_result_context(
            user_id="user-1",
            domain="sales",
            intent="sales_by_branch",
            title="ventas por sucursal",
            answer_text="resultado",
            dataframe=pd.DataFrame(
                [
                    {"Sucursal": "OAKLAND", "VentaNetaQ": 1000},
                    {"Sucursal": "BASSHERT", "VentaNetaQ": 100},
                ]
            ),
        )

        ranking_answer = answer_from_context("cual quedo peor?", "user-1")
        effective_question, _ = contextualize_question(
            "analiza esa sucursal y dame un plan de accion",
            "user-1",
        )

        self.assertIn("BASSHERT", ranking_answer or "")
        self.assertIn("BASSHERT", effective_question)
        self.assertIn("ventas", effective_question)
        self.assertNotIn("esa sucursal", effective_question.lower())

    def test_new_conversation_plan_for_branch_defaults_to_sales(self) -> None:
        effective_question, context = contextualize_question(
            "dame un plan de acion para basshert",
            "new-user",
        )

        self.assertIsNone(context)
        self.assertIn("ventas", effective_question)

    @patch("agents.kpi_agent.db.read_sql")
    def test_sales_summary_applies_branch_filter(self, read_sql: Mock) -> None:
        read_sql.return_value = pd.DataFrame(
            [
                {
                    "VentaNetaQ": 440,
                    "Unidades": 1,
                    "Facturas": 1,
                    "VentaBruta": 440,
                    "DescuentoQ": 0,
                    "CostoTotal": 377,
                    "MargenQ": 63,
                }
            ]
        )

        result = sales_summary("2026-06-05", "2026-06-05", "hoy", "BASSHERT")

        query, params = read_sql.call_args.args
        self.assertIn("Sucursal = ?", query)
        self.assertEqual(params[-1], "BASSHERT")
        self.assertIn("Ventas de BASSHERT", result.answer)

    @patch("services.maria_ai.requests.post")
    @patch("services.maria_ai._settings")
    def test_openai_response_enhances_answer(self, settings: Mock, post: Mock) -> None:
        settings.return_value = {
            "provider": "openai",
            "model": "gpt-5.5",
            "api_key": "test-key",
            "base_url": "https://api.openai.com/v1",
            "personality": "Responde en espanol.",
        }
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "Analisis gerencial."}],
                }
            ]
        }
        post.return_value = response

        result = enhance_answer(question="Analiza Basshert", base_answer="Venta Q 440")

        self.assertEqual(result, "Analisis gerencial.")
        self.assertTrue(post.called)

    @patch("services.maria_ai.requests.post")
    @patch("services.maria_ai._settings")
    def test_openai_cannot_reopen_resolved_branch_question(self, settings: Mock, post: Mock) -> None:
        settings.return_value = {
            "provider": "openai",
            "model": "gpt-5.5",
            "api_key": "test-key",
            "base_url": "https://api.openai.com/v1",
            "personality": "Responde en espanol.",
        }
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "¿A que sucursal te refieres?",
                        }
                    ],
                }
            ]
        }
        post.return_value = response

        result = enhance_answer(
            question="Analiza esa sucursal",
            base_answer="**Ventas de BASSHERT hoy**\n\nVenta Q 440",
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
