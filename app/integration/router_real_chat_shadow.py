from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone
import time

from app.agent_core.router_v1 import route_message
from app.integration.session_adapter_v1 import get_or_create_router_shadow_state

MAX_SESSION_RECORDS = 100


def observe_real_chat_turn(user_message: str, chat_session_state) -> dict:
    """Evaluate a real chat message without changing the production response path.

    This function invokes only the deterministic Agent Core router. It does not
    call retrieval, Chroma, embeddings, the LLM, or escalation persistence.
    Failures must be handled by the caller so production routing remains intact.
    """
    started=time.perf_counter()
    shadow_state=get_or_create_router_shadow_state(chat_session_state)
    decision=route_message(user_message,shadow_state)
    latency_ms=round((time.perf_counter()-started)*1000,3)
    return {
        "timestamp":datetime.now(timezone.utc).isoformat(),
        "input":user_message,
        "decision":asdict(decision),
        "shadow_state":asdict(shadow_state),
        "router_latency_ms":latency_ms,
        "llm_calls":0,
        "retrieval_calls":0,
        "production_response_changed":False,
        "observation_source":"real_chat_turn",
    }


def append_session_shadow_record(streamlit_session_state, record: dict) -> None:
    records=list(streamlit_session_state.get("agent_core_router_shadow_records",[]) or [])
    records.append(record)
    streamlit_session_state["agent_core_router_shadow_records"]=records[-MAX_SESSION_RECORDS:]
    streamlit_session_state["agent_core_router_shadow_last_record"]=record


def summarize_shadow_records(records: list[dict]) -> dict:
    route_counts={}; errors=0
    for record in records or []:
        route=str((record.get("decision") or {}).get("route") or "unknown")
        route_counts[route]=route_counts.get(route,0)+1
        errors+=int(bool(record.get("error")))
    return {
        "record_count":len(records or []),
        "route_counts":route_counts,
        "error_count":errors,
        "llm_calls":0,
        "retrieval_calls":0,
        "production_responses_changed":0,
    }
