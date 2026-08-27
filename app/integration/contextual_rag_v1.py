from __future__ import annotations
from datetime import datetime, timezone
import re
import time
from app.integration.session_adapter_v1 import get_or_create_router_shadow_state

GENERIC_CONTEXT_PATTERNS=(
    r"^el problema ocurre en ",
    r"^ocurre en ",
    r"^es en ",
)
SYMPTOM_TERMS=(
    "no imprime","no funciona","no aparece","desaparece","bloqueada","atascada",
    "retenido","retenidos","error","falla","offline","lento","no libera",
    "no registra","no escanea","no conecta","no responde","stuck","missing",
)


def _unique(values):
    result=[]
    for value in values or []:
        text=str(value or "").strip()
        if text and text not in result: result.append(text)
    return result


def _is_specific_symptom(value: str) -> bool:
    text=str(value or "").strip().lower()
    if not text: return False
    if any(re.search(pattern,text) for pattern in GENERIC_CONTEXT_PATTERNS): return False
    return any(term in text for term in SYMPTOM_TERMS)


def assess_context_readiness(chat_session_state) -> dict:
    state=get_or_create_router_shadow_state(chat_session_state)
    case=state.technical_case
    products=_unique(state.topic.products)
    symptom_candidates=_unique(case.symptoms)
    symptom_candidates.extend(
        _unique(fact.value for fact in case.context_facts if fact.fact_type in {"symptom","error_description"})
    )
    symptoms=_unique(value for value in symptom_candidates if _is_specific_symptom(value))
    missing=[]
    if not products: missing.append("product_or_tool")
    if not symptoms: missing.append("specific_symptom_or_error")
    return {
        "ready_for_rag":not missing,
        "missing_fields":missing,
        "products":products,
        "symptoms":symptoms,
        "clarification_response":None if not missing else (
            "Antes de buscar la siguiente validación necesito el síntoma concreto del caso. "
            "Indícame qué comportamiento observas, por ejemplo si el trabajo desaparece, queda retenido, "
            "no imprime, muestra un error o afecta una función específica. No necesitas repetir el producto "
            "ni las acciones que ya realizaste."
        ),
    }


def build_contextual_query(user_message: str, chat_session_state) -> dict:
    state=get_or_create_router_shadow_state(chat_session_state)
    case=state.technical_case
    readiness=assess_context_readiness(chat_session_state)
    products=readiness["products"]
    symptoms=readiness["symptoms"]
    processes=_unique(state.topic.processes)
    actions=_unique(case.attempted_actions)
    failed=_unique(case.failed_actions)
    negative_evidence=_unique(
        fact.value for fact in case.context_facts if fact.fact_type=="negative_evidence"
    )
    parts=[
        "Tipo de solicitud: troubleshooting técnico de soporte N1 para impresión.",
        "Objetivo: obtener la siguiente validación documentada para el síntoma confirmado.",
    ]
    if products: parts.append("Producto o herramienta: "+", ".join(products)+".")
    if processes: parts.append("Proceso relacionado: "+", ".join(processes)+".")
    if symptoms: parts.append("Síntoma confirmado: "+" | ".join(symptoms[-3:])+".")
    if negative_evidence: parts.append("Evidencia negativa: "+" | ".join(negative_evidence[-2:])+".")
    if actions: parts.append("Validaciones ya realizadas: "+" | ".join(actions[-3:])+".")
    if failed: parts.append("Acciones que no resolvieron el caso y no deben repetirse: "+" | ".join(failed[-3:])+".")
    if case.affected_users: parts.append("Alcance informado: "+str(case.affected_users)+".")
    parts.append("Solicitud actual: "+str(user_message).strip()+".")
    parts.append(
        "Responde como troubleshooting. Indica únicamente la siguiente validación o acción N1 soportada "
        "por las fuentes recuperadas. No cambies la intención a garantía, requisitos o procedimiento comercial. "
        "Si no existe una siguiente acción documentada, recomienda escalar e indica la evidencia técnica faltante."
    )
    return {
        "original_message":user_message,
        "contextual_query":" ".join(parts),
        "readiness":readiness,
        "products":products,
        "symptoms":symptoms,
        "processes":processes,
        "attempted_actions":actions,
        "failed_actions":failed,
        "affected_users":case.affected_users,
        "resolution_status":case.resolution_status,
        "state_turn_number":state.turn_number,
        "forced_intent":"troubleshooting",
    }


def append_contextual_record(streamlit_session_state, record: dict, limit: int=100):
    records=list(streamlit_session_state.get("agent_core_contextual_records",[]) or [])
    records.append(record)
    streamlit_session_state["agent_core_contextual_records"]=records[-limit:]
    streamlit_session_state["agent_core_contextual_last_record"]=record


def preview_contextual_query(user_message: str, chat_session_state) -> dict:
    started=time.perf_counter(); record=build_contextual_query(user_message,chat_session_state)
    record.update({
        "timestamp":datetime.now(timezone.utc).isoformat(),
        "builder_latency_ms":round((time.perf_counter()-started)*1000,3),
        "rag_called":False,
        "llm_called":False,
    })
    return record
