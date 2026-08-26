from __future__ import annotations
from dataclasses import asdict
from app.agent_core.router_v1 import route_message
from app.integration.session_adapter_v1 import get_or_create_router_shadow_state

def evaluate_router_shadow(message: str,chat_session_state) -> dict:
    state=get_or_create_router_shadow_state(chat_session_state);decision=route_message(message,state)
    return {"decision":asdict(decision),"state":asdict(state),"llm_calls":0,"retrieval_calls":0,"production_response_changed":False}
