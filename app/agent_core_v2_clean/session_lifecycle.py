from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable
import secrets,time

@dataclass
class SessionRuntime:
    session_id: str = field(default_factory=lambda: secrets.token_hex(12))
    created_at: float = field(default_factory=time.time)
    telemetry: dict[str, Any] = field(default_factory=dict)
    caches: dict[str, Any] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)

def new_runtime() -> SessionRuntime:
    return SessionRuntime(telemetry={"schema_version":2,"calls":0,"provider_failed_calls":0,"contract_failed_calls":0,"functional_failed_calls":0,"prompt_tokens":0,"completion_tokens":0,"total_tokens":0,"latency_ms":0.0,"by_purpose":{},"last_rate_limit":None},caches={},diagnostics={"reset_reason":"new_conversation"})

def reset_new_conversation(state: dict[str,Any], *, cache_clearers: list[Callable[[],None]]|None=None) -> SessionRuntime:
    """Reset every conversation-scoped object without restarting Streamlit.

    Shared production objects such as vector stores, backend clients and model
    configuration are intentionally not touched.
    """
    for clear in cache_clearers or []:
        clear()
    prefixes=("v2_clean_","agent_core_v2_clean_")
    explicit={"messages","turns","state","telemetry","session_metrics","turn_metrics","cache_metrics","conversation_id","budget_runtime","last_export","last_error"}
    for key in list(state):
        if key in explicit or key.startswith(prefixes):
            state.pop(key,None)
    runtime=new_runtime()
    state["agent_core_v2_clean_runtime"]=runtime
    state["messages"]=[];state["turns"]=[];state["telemetry"]=runtime.telemetry
    return runtime

def budget_snapshot(runtime: SessionRuntime, max_tokens:int, reserve_tokens:int) -> dict[str,Any]:
    used=int((runtime.telemetry or {}).get("total_tokens",0));remaining=max(0,int(max_tokens)-used)
    return {"session_id":runtime.session_id,"used_tokens":used,"max_tokens":int(max_tokens),"reserve_tokens":int(reserve_tokens),"remaining_tokens":remaining,"available_after_reserve":max(0,remaining-int(reserve_tokens))}
