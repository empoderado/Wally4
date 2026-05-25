from __future__ import annotations


FORBIDDEN_RESPONSE = "Por favor por seguridad primero discuteelo con el administrador."


def requires_approval(action: str) -> bool:
    return action in {"send_email", "schedule_task", "automatic_alert", "generate_report"}
