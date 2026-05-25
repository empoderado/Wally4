from __future__ import annotations

from agents.intent_router import detect_intent
from agents.intent_router import normalize_text
from agents.analytical_agent import try_answer as try_analytical_answer
from agents.analytical_agent import try_result as try_analytical_result
from agents.analytical_agent import should_prefer_analytical
from agents.kpi_agent import (
    best_customer,
    inventory_by_branch,
    inventory_by_shipment,
    inventory_reference,
    sales_by_branch,
    sales_by_line,
    sales_by_seller,
    sales_by_shipment,
    sales_summary,
    sales_year_comparison,
)
from agents.security import FORBIDDEN_RESPONSE
from agents.sql_agent import parse_query_context
from agents.strategy_agent import StrategyContext
from agents.strategy_agent import strategy_from_previous
from agents.strategy_agent import strategy_from_result
from agents.strategy_agent import wants_previous_context
from agents.strategy_agent import wants_strategy
from agents.temporal_agent import resolve_date_range
from memory.store import answer_memory_question
from memory.store import apply_memory_to_question
from memory.store import log_conversation
from memory.store import try_capture_memory


def answer(question: str, channel: str = "app", user_id: str = "", user_name: str = "") -> str:
    clean_question = question.strip()
    memory_response = try_capture_memory(clean_question, user_id=user_id)
    if memory_response:
        log_conversation(
            channel=channel,
            user_id=user_id,
            user_name=user_name,
            question=clean_question,
            answer=memory_response,
            intent="memory_capture",
        )
        return memory_response

    memory_question_response = answer_memory_question(clean_question, user_id=user_id)
    if memory_question_response:
        log_conversation(
            channel=channel,
            user_id=user_id,
            user_name=user_name,
            question=clean_question,
            answer=memory_question_response,
            intent="memory_read",
        )
        return memory_question_response

    effective_question = apply_memory_to_question(clean_question, user_id=user_id)
    used_memory_context = effective_question != clean_question
    intent = detect_intent(effective_question)

    try:
        if wants_strategy(effective_question) and wants_previous_context(effective_question):
            previous_strategy = strategy_from_previous(user_id=user_id)
            response = previous_strategy or _unknown_response()
        else:
            analytical_result = try_analytical_result(effective_question) if used_memory_context or should_prefer_analytical(effective_question, intent) else None
            if analytical_result:
                response = _maybe_append_strategy(
                    effective_question,
                    analytical_result.answer,
                    analytical_result.dataframe,
                    analytical_result.plan.title,
                )
            elif intent == "forbidden":
                response = FORBIDDEN_RESPONSE
            elif intent == "sales_summary":
                dates = resolve_date_range(effective_question)
                result = sales_summary(dates.start, dates.end, dates.label)
                response = _maybe_append_strategy(effective_question, result.answer, result.dataframe, "ventas")
            elif intent == "sales_by_branch":
                dates = resolve_date_range(effective_question)
                result = sales_by_branch(dates.start, dates.end, dates.label)
                response = _maybe_append_strategy(effective_question, result.answer, result.dataframe, "ventas por sucursal")
            elif intent == "sales_by_seller":
                dates = resolve_date_range(effective_question)
                context = parse_query_context(effective_question)
                result = sales_by_seller(dates.start, dates.end, dates.label, context.limit)
                response = _maybe_append_strategy(effective_question, result.answer, result.dataframe, "ventas por vendedor")
            elif intent == "sales_by_shipment":
                dates = resolve_date_range(effective_question)
                context = parse_query_context(effective_question)
                result = sales_by_shipment(dates.start, dates.end, dates.label, context.limit)
                response = _maybe_append_strategy(effective_question, result.answer, result.dataframe, "ventas por embarque")
            elif intent == "sales_by_line":
                dates = resolve_date_range(effective_question)
                context = parse_query_context(effective_question)
                result = sales_by_line(dates.start, dates.end, dates.label, context.limit)
                response = _maybe_append_strategy(effective_question, result.answer, result.dataframe, "ventas por linea")
            elif intent == "sales_year_comparison":
                result = sales_year_comparison()
                response = _maybe_append_strategy(effective_question, result.answer, result.dataframe, "comparativo anual")
            elif intent == "best_customer":
                dates = resolve_date_range(effective_question)
                context = parse_query_context(effective_question)
                normalized = normalize_text(effective_question)
                order_by = "facturas" if any(term in normalized for term in ["veces", "comprado", "compraron", "frecuencia", "frecuente"]) else "venta"
                result = best_customer(dates.start, dates.end, dates.label, context.limit, order_by)
                response = _maybe_append_strategy(effective_question, result.answer, result.dataframe, "clientes")
            elif intent == "inventory_by_branch":
                result = inventory_by_branch()
                response = _maybe_append_strategy(effective_question, result.answer, result.dataframe, "inventario por sucursal")
            elif intent == "inventory_by_shipment":
                context = parse_query_context(effective_question)
                result = inventory_by_shipment(context.limit)
                response = _maybe_append_strategy(effective_question, result.answer, result.dataframe, "inventario por embarque")
            elif intent == "inventory_reference":
                context = parse_query_context(effective_question)
                result = inventory_reference(context)
                response = _maybe_append_strategy(effective_question, result.answer, result.dataframe, "inventario por referencia")
            elif intent == "help":
                response = _help_response()
            else:
                response = try_analytical_answer(effective_question) or _unknown_response()
    except PermissionError:
        response = FORBIDDEN_RESPONSE
    except Exception as exc:
        response = f"No pude responder con datos de Wally. Detalle tecnico controlado: {exc}"

    log_conversation(
        channel=channel,
        user_id=user_id,
        user_name=user_name,
        question=clean_question,
        answer=response,
        intent=intent,
    )
    return response


def _help_response() -> str:
    return (
        "Puedo consultar informacion autorizada de Wally.\n\n"
        "Ejemplos:\n\n"
        "1. Ventas hoy\n\n"
        "2. Dame la venta de ayer\n\n"
        "3. Ventas por sucursal de la semana pasada\n\n"
        "4. Ventas por vendedor de ayer\n\n"
        "5. Ventas por embarque del mes\n\n"
        "6. Comparativo anual de ventas\n\n"
        "7. Inventario por embarque\n\n"
        "8. Inventario de la referencia S506345 en Pradera\n\n"
        "9. Cual es el mejor cliente de este mes\n\n"
        "10. Tambien puedo intentar consultas analiticas como: top referencias mas vendidas, ventas por tipo de prenda, inventario por color o margen por linea.\n\n"
        "11. Tambien puedes pedirme analisis estrategico o plan de accion sobre cualquier resultado."
    )


def _unknown_response() -> str:
    return (
        "Todavia no tengo una ruta segura para responder esa pregunta.\n\n"
        "Prueba con ventas hoy, ventas por sucursal, ventas por vendedor, mejor cliente, comparativo anual, inventario de una referencia o una consulta analitica sobre ventas e inventario."
    )


def _maybe_append_strategy(question: str, response: str, dataframe, title: str) -> str:
    if not wants_strategy(question):
        return response
    strategy = strategy_from_result(question, StrategyContext(title=title, dataframe=dataframe, answer_text=response))
    return f"{response}\n\n{strategy}"
