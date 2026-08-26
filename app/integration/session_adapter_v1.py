from __future__ import annotations
from app.agent_core.router_models import RouterShadowState

ATTRIBUTE_NAME="agent_core_v1_shadow_state"

def get_or_create_router_shadow_state(chat_session_state) -> RouterShadowState:
    current=getattr(chat_session_state,ATTRIBUTE_NAME,None)
    if isinstance(current,RouterShadowState): return current
    current=RouterShadowState(); setattr(chat_session_state,ATTRIBUTE_NAME,current); return current

def reset_router_shadow_state(chat_session_state) -> RouterShadowState:
    current=RouterShadowState(); setattr(chat_session_state,ATTRIBUTE_NAME,current); return current
