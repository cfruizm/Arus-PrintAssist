from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone
import time

from app.integration.session_adapter_v1 import get_or_create_router_shadow_state


def _unique(values):
    output=[]
    for value in values or []:
        text=str(value or "").strip()
        if text and text not in output: output.append(text)
    return output


def build_contextual_query(user_message: str, chat_session_state) -> dict:
    """Build one grounded technical query from Agent Core state.

    The visible user message is preserved separately. The generated query is
    used only by the existing RAG pipeline and contains no invented facts.
    """
    state=get_or_create_router_shadow_state(chat_session_state)
    case=state.technical_case
    products=_unique(state.topic.products)
    processes=_unique(state.topic.processes)
    actions=_unique(case.attempted_actions)
    failed=_unique(case.failed_actions)
    facts=[]
    for fact in case.context_facts:
        if fact.fact_type in {"technical_context","negative_evidence","affected_scope"}:
            facts.append(str(fact.value))
    facts=_unique(facts)

    parts=["Necesito la siguiente orientación técnica documentada para un caso de soporte de impresión."]
    if products: parts.append("Producto o herramienta: " + ", ".join(products) + ".")
    if processes: parts.append("Proceso relacionado: " + ", ".join(processes) + ".")
    if facts: parts.append("Contexto confirmado por el usuario: " + " | ".join(facts[-4:]) + ".")
    if actions: parts.append("Validaciones o acciones ya realizadas: " + " | ".join(actions[-3:]) + ".")
    if failed: parts.append("Las siguientes acciones no resolvieron el caso: " + " | ".join(failed[-3:]) + ".")
    if case.affected_users: parts.append("Alcance informado: " + str(case.affected_users) + ".")
    if case.resolution_status: parts.append("Estado de resolución: " + str(case.resolution_status) + ".")
    parts.append("Solicitud actual del usuario: " + str(user_message).strip() + ".")
    parts.append("Indica únicamente la siguiente validación o acción N1 soportada por la documentación, sin repetir acciones fallidas ni inventar procedimientos. Si no existe una siguiente acción documentada, indica que corresponde escalar y qué evidencia falta.")
    query=" ".join(parts)
    return {
        "original_message":user_message,
        "contextual_query":query,
        "products":products,
        "processes":processes,
        "attempted_actions":actions,
        "failed_actions":failed,
        "affected_users":case.affected_users,
        "resolution_status":case.resolution_status,
        "state_turn_number":state.turn_number,
    }


def evaluate_contextual_request(user_message: str, chat_session_state) -> dict:
    started=time.perf_counter(); payload=build_contextual_query(user_message,chat_session_state)
    payload.update({
        "timestamp":datetime.now(timezone.utc).isoformat(),
        "builder_latency_ms":round((time.perf_counter()-started)*1000,3),
        "rag_called":False,
        "llm_called":False,
    })
    return payload


def append_contextual_record(streamlit_session_state, record, limit=100):
    records=list(streamlit_session_state.get("agent_core_contextual_records",[]) or [])
    records.append(record)
    streamlit_session_state["agent_core_contextual_records"]=records[-limit:]
    streamlit_session_state["agent_core_contextual_last_record"]=record
