from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone
import time

from app.agent_core.router_v1 import route_message
from app.integration.session_adapter_v1 import get_or_create_router_shadow_state

AUTHORIZED_ROUTES = frozenset({
    "social",
    "capabilities",
    "support_intake",
    "case_update",
    "clarification",
})


def evaluate_deterministic_activation(user_message: str, chat_session_state) -> dict:
    """Evaluate one turn and authorize only low-risk deterministic routes."""
    started=time.perf_counter()
    agent_state=get_or_create_router_shadow_state(chat_session_state)
    decision=route_message(user_message,agent_state)
    authorized=(
        decision.route in AUTHORIZED_ROUTES
        and bool(decision.deterministic_response)
        and not decision.use_retrieval
        and not decision.use_llm
    )
    return {
        "timestamp":datetime.now(timezone.utc).isoformat(),
        "input":user_message,
        "decision":asdict(decision),
        "agent_state":asdict(agent_state),
        "authorized":authorized,
        "response":decision.deterministic_response if authorized else None,
        "fallback_to_legacy":not authorized,
        "router_latency_ms":round((time.perf_counter()-started)*1000,3),
        "additional_llm_calls":0,
        "additional_retrieval_calls":0,
    }


def append_activation_record(streamlit_session_state, record: dict, limit: int=100) -> None:
    records=list(streamlit_session_state.get("agent_core_deterministic_records",[]) or [])
    records.append(record)
    streamlit_session_state["agent_core_deterministic_records"]=records[-limit:]
    streamlit_session_state["agent_core_deterministic_last_record"]=record


def summarize_activation_records(records: list[dict]) -> dict:
    route_counts={};authorized=0;fallback=0;errors=0
    for record in records or []:
        route=str((record.get("decision") or {}).get("route") or "error")
        route_counts[route]=route_counts.get(route,0)+1
        authorized+=int(bool(record.get("authorized")))
        fallback+=int(bool(record.get("fallback_to_legacy")))
        errors+=int(bool(record.get("error")))
    return {"record_count":len(records or []),"authorized_count":authorized,"fallback_count":fallback,"error_count":errors,"route_counts":route_counts,"additional_llm_calls":0,"additional_retrieval_calls":0}
