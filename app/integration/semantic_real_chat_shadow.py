from __future__ import annotations
from datetime import datetime,timezone
import time
from app.agent_core.semantic_gateway_evaluator import extract_json,normalize,derive_protocol
from app.agent_core.semantic_gateway_prompt import build_messages
from app.agent_core.semantic_gateway_schema import SEMANTIC_DECISION_SCHEMA
from app.agent_core.conversation_act_runtime import compact_case_state,sanitize_semantic_decision
from app.agent_core.semantic_state_runtime import apply_semantic_state_updates
from app.integration.session_adapter_v1 import get_or_create_router_shadow_state
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway
from app.llm_gateway.models import LLMRequest

MAX_RECORDS=100
CACHE_SECONDS=15.0
NEXT_STEP_MARKERS=("siguiente paso","que hago","qué hago","como continuo","cómo continúo","como sigo","cómo sigo","que mas","qué más","otra validacion","otra validación","otra accion","otra acción","ahora que","ahora qué")

def _norm(value): return " ".join(str(value or "").casefold().strip().split())
def _has_explicit_request(message):
    text=_norm(message)
    return "?" in str(message or "") or any(marker in text for marker in NEXT_STEP_MARKERS)

def normalize_act_against_current_message(data,user_message):
    normalized=dict(data or {}); updates=list(normalized.get("state_updates") or []); types={str(i.get("type") or "") for i in updates if isinstance(i,dict)}; act=str(normalized.get("conversation_act") or ""); correction=None
    if act=="report_failed_attempt_and_request_next_step" and "attempted_action" in types and "attempt_result" not in types and not _has_explicit_request(user_message):
        normalized["conversation_act"]="provide_case_detail"; normalized["response_mode"]="deterministic"; normalized["retrieval_request"]=None; normalized["clarification_question"]=None; correction="performed_action_without_result_or_request"
    return normalized,correction

def get_cached_semantic_turn(user_message,streamlit_session_state):
    cache=streamlit_session_state.get("agent_core_semantic_turn_cache") or {}
    if cache.get("input")!=str(user_message or ""): return None
    try: age=time.monotonic()-float(cache.get("monotonic",0.0))
    except Exception: return None
    if 0<=age<=CACHE_SECONDS and isinstance(cache.get("record"),dict):
        reused=dict(cache["record"]); reused["semantic_cache_reused"]=True; reused["semantic_cache_age_ms"]=round(age*1000,3); return reused
    return None

def observe_semantic_real_chat_turn(user_message,chat_session_state,streamlit_session_state,secrets)->dict:
    cached=get_cached_semantic_turn(user_message,streamlit_session_state)
    if cached is not None: return cached
    started=time.perf_counter(); router_state=get_or_create_router_shadow_state(chat_session_state); case_state=compact_case_state(router_state); config=load_gateway_config(secrets); max_tokens=max(96,min(220,int(secrets.get("LLM_ORCHESTRATOR_MAX_TOKENS",180))))
    result=LLMGateway(config,streamlit_session_state).complete(LLMRequest(build_messages(user_message,case_state),"semantic_orchestrator",max_tokens,0.0,SEMANTIC_DECISION_SCHEMA))
    record={"timestamp":datetime.now(timezone.utc).isoformat(),"input":user_message,"case_state_before":case_state,"provider_result":result.to_dict(),"production_response_changed":False,"retrieval_executed":False,"state_applied_to_production":False,"semantic_cache_reused":False}
    if result.ok:
        try:
            raw=normalize(extract_json(result.text)); corrected,correction=normalize_act_against_current_message(raw,user_message); derived=derive_protocol(corrected,case_state); clean=sanitize_semantic_decision(corrected,derived,case_state); normalized_decision=clean["normalized_decision"]; enabled=bool(secrets.get("AGENT_CORE_SEMANTIC_APPLY_STATE",False))
            try: threshold=max(.5,min(1.0,float(secrets.get("AGENT_CORE_SEMANTIC_STATE_MIN_CONFIDENCE",.75))))
            except Exception: threshold=.75
            application={"attempted":0,"applied":[],"skipped":[],"changed":False,"minimum_confidence":threshold,"enabled":enabled}
            if enabled: application.update(apply_semantic_state_updates(router_state,normalized_decision,minimum_confidence=threshold))
            record.update({"status":"ok","model_decision":raw,"corrected_decision":corrected,"semantic_act_correction":correction,"derived_decision":derived,**clean,"state_application":application,"state_applied_to_production":bool(application.get("changed")),"case_state_after":compact_case_state(router_state)})
        except Exception as exc: record.update({"status":"invalid_output","validation_error":f"{type(exc).__name__}: {exc}"})
    else: record["status"]="provider_error"
    record["total_shadow_latency_ms"]=round((time.perf_counter()-started)*1000,3); records=list(streamlit_session_state.get("agent_core_semantic_real_chat_records",[]) or []); records.append(record); streamlit_session_state["agent_core_semantic_real_chat_records"]=records[-MAX_RECORDS:]; streamlit_session_state["agent_core_semantic_real_chat_last_record"]=record; streamlit_session_state["agent_core_semantic_turn_cache"]={"input":str(user_message or ""),"monotonic":time.monotonic(),"record":record}
    return record

def summarize_records(records):
    return {"total":len(records),"ok":sum(r.get("status")=="ok" for r in records),"provider_errors":sum(r.get("status")=="provider_error" for r in records),"invalid_outputs":sum(r.get("status")=="invalid_output" for r in records),"normalizations":sum(bool(r.get("normalization_applied")) for r in records),"total_tokens":sum(int(r.get("provider_result",{}).get("usage",{}).get("total_tokens",0) or 0) for r in records),"production_responses_changed":0,"semantic_retrieval_executions":0,"semantic_cache_reuses":sum(bool(r.get("semantic_cache_reused")) for r in records)}
