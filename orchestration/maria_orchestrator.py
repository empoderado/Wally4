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
from memory.store import memory_summary
from memory.store import try_capture_memory
from memory.conversation_context import answer_from_context
from memory.conversation_context import context_summary
from memory.conversation_context import contextualize_question
from memory.conversation_context import dates_from_context
from memory.conversation_context import save_result_context
from services.maria_ai import enhance_answer
from services.maria_ai import is_configured as ai_is_configured


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

    context_response = answer_from_context(clean_question, user_id=user_id)
    if context_response:
        log_conversation(
            channel=channel,
            user_id=user_id,
            user_name=user_name,
            question=clean_question,
            answer=context_response,
            intent="context_read",
        )
        return context_response

    memory_question = apply_memory_to_question(clean_question, user_id=user_id)
    effective_question, conversation_context = contextualize_question(memory_question, user_id=user_id)
    intent = detect_intent(effective_question)
    query_context = parse_query_context(effective_question)

    try:
        if wants_strategy(effective_question) and wants_previous_context(effective_question):
            previous_strategy = strategy_from_previous(user_id=user_id)
            response = previous_strategy or _unknown_response()
        else:
            analytical_result = try_analytical_result(effective_question) if should_prefer_analytical(effective_question, intent) else None
            if analytical_result:
                response = _maybe_append_strategy(
                    effective_question,
                    analytical_result.answer,
                    analytical_result.dataframe,
                    analytical_result.plan.title,
                )
                analytical_dates = dates_from_context(clean_question, conversation_context)
                if analytical_result.plan.date_column and not analytical_dates:
                    analytical_dates = resolve_date_range(effective_question)
                save_result_context(
                    user_id=user_id,
                    domain="inventory" if "inventario" in normalize_text(analytical_result.plan.title) else "sales",
                    intent=intent,
                    title=analytical_result.plan.title,
                    answer_text=response,
                    dataframe=analytical_result.dataframe,
                    dates=analytical_dates,
                    branch=query_context.branch,
                    reference=query_context.reference,
                )
            elif intent == "forbidden":
                response = FORBIDDEN_RESPONSE
            elif intent == "sales_summary":
                dates = dates_from_context(clean_question, conversation_context) or resolve_date_range(effective_question)
                result = sales_summary(dates.start, dates.end, dates.label, query_context.branch)
                response = _maybe_append_strategy(effective_question, result.answer, result.dataframe, "ventas")
                save_result_context(
                    user_id=user_id,
                    domain="sales",
                    intent=intent,
                    title="ventas",
                    answer_text=response,
                    dataframe=result.dataframe,
                    dates=dates,
                    branch=query_context.branch,
                )
            elif intent == "sales_by_branch":
                dates = dates_from_context(clean_question, conversation_context) or resolve_date_range(effective_question)
                normalized = normalize_text(effective_question)
                product_filters, product_label = _seller_product_filters(normalized)
                order_by = "units" if any(
                    term in normalized
                    for term in ["cuanto", "cuantos", "cantidad", "unidad", "unidades"]
                ) else "sales"
                result = sales_by_branch(
                    dates.start,
                    dates.end,
                    dates.label,
                    query_context.limit,
                    product_filters=product_filters,
                    product_label=product_label,
                    order_by=order_by,
                )
                response = _maybe_append_strategy(effective_question, result.answer, result.dataframe, "ventas por sucursal")
                save_result_context(
                    user_id=user_id,
                    domain="sales",
                    intent=intent,
                    title="ventas por sucursal",
                    answer_text=response,
                    dataframe=result.dataframe,
                    dates=dates,
                )
            elif intent == "sales_by_seller":
                dates = dates_from_context(clean_question, conversation_context) or resolve_date_range(effective_question)
                normalized = normalize_text(effective_question)
                ascending = any(
                    term in normalized
                    for term in [
                        "peor",
                        "vendio menos",
                        "menor venta",
                        "menos venta",
                        "ultimas",
                        "ultima asesora",
                        "ultima vendedora",
                    ]
                )
                seller_product_filters, seller_product_label = _seller_product_filters(normalized)
                seller_order_by = "units" if any(
                    term in normalized
                    for term in ["unidad", "unidades", "piezas", "cantidad"]
                ) else "sales"
                result = sales_by_seller(
                    dates.start,
                    dates.end,
                    dates.label,
                    query_context.limit,
                    ascending=ascending,
                    branch=query_context.branch,
                    product_filters=seller_product_filters,
                    product_label=seller_product_label,
                    order_by=seller_order_by,
                )
                response = _maybe_append_strategy(effective_question, result.answer, result.dataframe, "ventas por vendedor")
                _save_context(user_id, "sales", intent, "ventas por vendedor", response, result.dataframe, dates, query_context)
            elif intent == "sales_by_shipment":
                dates = dates_from_context(clean_question, conversation_context) or resolve_date_range(effective_question)
                result = sales_by_shipment(dates.start, dates.end, dates.label, query_context.limit)
                response = _maybe_append_strategy(effective_question, result.answer, result.dataframe, "ventas por embarque")
                _save_context(user_id, "sales", intent, "ventas por embarque", response, result.dataframe, dates, query_context)
            elif intent == "sales_by_line":
                dates = dates_from_context(clean_question, conversation_context) or resolve_date_range(effective_question)
                result = sales_by_line(dates.start, dates.end, dates.label, query_context.limit)
                response = _maybe_append_strategy(effective_question, result.answer, result.dataframe, "ventas por linea")
                _save_context(user_id, "sales", intent, "ventas por linea", response, result.dataframe, dates, query_context)
            elif intent == "sales_year_comparison":
                result = sales_year_comparison()
                response = _maybe_append_strategy(effective_question, result.answer, result.dataframe, "comparativo anual")
                _save_context(user_id, "sales", intent, "comparativo anual", response, result.dataframe, None, query_context)
            elif intent == "best_customer":
                dates = dates_from_context(clean_question, conversation_context) or resolve_date_range(effective_question)
                normalized = normalize_text(effective_question)
                order_by = "facturas" if any(term in normalized for term in ["veces", "comprado", "compraron", "frecuencia", "frecuente"]) else "venta"
                result = best_customer(dates.start, dates.end, dates.label, query_context.limit, order_by)
                response = _maybe_append_strategy(effective_question, result.answer, result.dataframe, "clientes")
                _save_context(user_id, "sales", intent, "clientes", response, result.dataframe, dates, query_context)
            elif intent == "inventory_by_branch":
                result = inventory_by_branch()
                response = _maybe_append_strategy(effective_question, result.answer, result.dataframe, "inventario por sucursal")
                save_result_context(
                    user_id=user_id,
                    domain="inventory",
                    intent=intent,
                    title="inventario por sucursal",
                    answer_text=response,
                    dataframe=result.dataframe,
                    branch=query_context.branch,
                )
            elif intent == "inventory_by_shipment":
                result = inventory_by_shipment(query_context.limit)
                response = _maybe_append_strategy(effective_question, result.answer, result.dataframe, "inventario por embarque")
                _save_context(user_id, "inventory", intent, "inventario por embarque", response, result.dataframe, None, query_context)
            elif intent == "inventory_reference":
                result = inventory_reference(query_context)
                response = _maybe_append_strategy(effective_question, result.answer, result.dataframe, "inventario por referencia")
                _save_context(user_id, "inventory", intent, "inventario por referencia", response, result.dataframe, None, query_context)
            elif intent == "help":
                response = _help_response()
            else:
                response = try_analytical_answer(effective_question) or _unknown_response()
    except PermissionError:
        response = FORBIDDEN_RESPONSE
    except Exception as exc:
        response = f"No pude responder con datos de Wally. Detalle tecnico controlado: {exc}"

    if ai_is_configured() and _should_enhance_with_ai(clean_question, intent, response):
        ai_response = enhance_answer(
            question=clean_question,
            base_answer=response,
            conversation_summary=context_summary(user_id),
            memory_summary=memory_summary(user_id=user_id),
        )
        if ai_response:
            response = ai_response

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


def _save_context(user_id, domain, intent, title, response, dataframe, dates, query_context) -> None:
    save_result_context(
        user_id=user_id,
        domain=domain,
        intent=intent,
        title=title,
        answer_text=response,
        dataframe=dataframe,
        dates=dates,
        branch=query_context.branch,
        reference=query_context.reference,
    )


def _seller_product_filters(normalized: str) -> tuple[list[tuple[str, str]], str | None]:
    filters: list[tuple[str, str]] = []
    labels: list[str] = []

    explicit_merchan = any(
        term in normalized
        for term in [
            "linea merchan",
            "linea merchant",
            "linea merchand",
            "agrupacion merchan",
            "agrupacion merchant",
            "agrupacion merchand",
            "tipo merchan",
            "tipo merchant",
            "tipo merchand",
            "merchan",
            "merchant",
            "merchand",
            "merchandising",
        ]
    )
    if explicit_merchan:
        return [
            ("Linea", "MERCHAN"),
            ("DescripTipoPrenda", "MERCHAN"),
            ("Descripcion3Tabla4", "MERCHAN"),
        ], "Merchan"

    if any(term in normalized for term in ["jean", "jeans"]):
        filters.append(("Linea", "JEAN"))
        labels.append("Jean")

    if any(term in normalized for term in ["bolso", "bolsos"]):
        filters.extend(
            [
                ("Linea", "BOLSO%"),
                ("DescripTipoPrenda", "BOLSOS"),
                ("Descripcion3Tabla4", "BOLSOS"),
            ]
        )
        labels.append("Bolsos")

    unique_filters = list(dict.fromkeys(filters))
    unique_labels = list(dict.fromkeys(labels))
    return unique_filters, " / ".join(unique_labels) if unique_labels else None


def _should_enhance_with_ai(question: str, intent: str, response: str) -> bool:
    if intent == "forbidden" or response == FORBIDDEN_RESPONSE or response.startswith("No pude responder con datos"):
        return False
    normalized = normalize_text(question)
    return (
        intent == "unknown"
        or wants_strategy(question)
        or any(
            term in normalized
            for term in [
                "por que",
                "explica",
                "interpreta",
                "compara",
                "comparala",
                "que significa",
                "que recomiendas",
            ]
        )
    )
