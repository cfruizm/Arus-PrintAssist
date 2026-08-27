from __future__ import annotations
from datetime import datetime, timezone
import time
from app.integration.session_adapter_v1 import get_or_create_router_shadow_state

def _unique(values):
    result=[]
    for value in values or []:
        text=str(value or "").strip()
        if text and text not in result: result.append(text)
    return result

def build_contextual_query(user_message: str, chat_session_state) -> dict:
    state=get_or_create_router_shadow_state(chat_session_state)
    case=state.technical_case
    products=_unique(state.topic.products)
    processes=_unique(state.topic.processes)
    actions=_unique(case.attempted_actions)
    failed=_unique(case.failed_actions)
    facts=_unique([fact.value for fact in case.context_facts if fact.fact_type in {"technical_context","negative_evidence","affected_scope"}])
    parts=["Necesito la siguiente orientación técnica documentada para un caso de soporte de impresión."]
    if products: parts.append("Producto o herramienta: "+", ".join(products)+".")
    if processes: parts.append("Proceso relacionado: "+", ".join(processes)+".")
    if facts: parts.append("Contexto confirmado por el usuario: "+" | ".join(facts[-4:])+".")
    if actions: parts.append("Validaciones o acciones ya realizadas: "+" | ".join(actions[-3:])+".")
    if failed: parts.append("Acciones que no resolvieron el caso: "+" | ".join(failed[-3:])+".")
    if case.affected_users: parts.append("Alcance informado: "+str(case.affected_users)+".")
    if case.resolution_status: parts.append("Estado de resolución: "+str(case.resolution_status)+".")
    parts.append("Solicitud actual: "+str(user_message).strip()+".")
    parts.append("Indica solo la siguiente validación o acción N1 soportada por la documentación. No repitas acciones fallidas. Si no existe una acción adicional documentada, recomienda escalar e indica la evidencia faltante.")
    return {"original_message":user_message,"contextual_query":" ".join(parts),"products":products,"processes":processes,"attempted_actions":actions,"failed_actions":failed,"affected_users":case.affected_users,"resolution_status":case.resolution_status,"state_turn_number":state.turn_number}

def append_contextual_record(streamlit_session_state, record: dict, limit: int=100):
    records=list(streamlit_session_state.get("agent_core_contextual_records",[]) or [])
    records.append(record)
    streamlit_session_state["agent_core_contextual_records"]=records[-limit:]
    streamlit_session_state["agent_core_contextual_last_record"]=record

def preview_contextual_query(user_message: str, chat_session_state) -> dict:
    started=time.perf_counter(); record=build_contextual_query(user_message,chat_session_state)
    record.update({"timestamp":datetime.now(timezone.utc).isoformat(),"builder_latency_ms":round((time.perf_counter()-started)*1000,3),"rag_called":False,"llm_called":False})
    return record
