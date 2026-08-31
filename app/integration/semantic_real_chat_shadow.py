from __future__ import annotations
from datetime import datetime,timezone
import time
from app.agent_core.semantic_gateway_evaluator import extract_json,normalize,derive_protocol
from app.agent_core.semantic_gateway_prompt import build_messages
from app.agent_core.semantic_gateway_schema import SEMANTIC_DECISION_SCHEMA
from app.agent_core.conversation_act_runtime import compact_case_state,sanitize_semantic_decision
from app.integration.session_adapter_v1 import get_or_create_router_shadow_state
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway
from app.llm_gateway.models import LLMRequest

MAX_RECORDS=100

def observe_semantic_real_chat_turn(user_message,chat_session_state,streamlit_session_state,secrets)->dict:
    started=time.perf_counter();router_state=get_or_create_router_shadow_state(chat_session_state);case_state=compact_case_state(router_state)
    config=load_gateway_config(secrets);max_tokens=max(96,min(220,int(secrets.get("LLM_ORCHESTRATOR_MAX_TOKENS",180))))
    result=LLMGateway(config,streamlit_session_state).complete(LLMRequest(build_messages(user_message,case_state),"semantic_orchestrator",max_tokens,0.0,SEMANTIC_DECISION_SCHEMA))
    record={"timestamp":datetime.now(timezone.utc).isoformat(),"input":user_message,"case_state_before":case_state,"provider_result":result.to_dict(),"production_response_changed":False,"retrieval_executed":False,"state_applied_to_production":False}
    if result.ok:
        try:
            raw=normalize(extract_json(result.text));derived=derive_protocol(raw,case_state);clean=sanitize_semantic_decision(raw,derived,case_state)
            record.update({"status":"ok","model_decision":raw,"derived_decision":derived,**clean})
        except Exception as exc:record.update({"status":"invalid_output","validation_error":f"{type(exc).__name__}: {exc}"})
    else:record["status"]="provider_error"
    record["total_shadow_latency_ms"]=round((time.perf_counter()-started)*1000,3)
    records=list(streamlit_session_state.get("agent_core_semantic_real_chat_records",[]) or []);records.append(record);streamlit_session_state["agent_core_semantic_real_chat_records"]=records[-MAX_RECORDS:];streamlit_session_state["agent_core_semantic_real_chat_last_record"]=record
    return record

def summarize_records(records):
    return {"total":len(records),"ok":sum(r.get("status")=="ok" for r in records),"provider_errors":sum(r.get("status")=="provider_error" for r in records),"invalid_outputs":sum(r.get("status")=="invalid_output" for r in records),"normalizations":sum(bool(r.get("normalization_applied")) for r in records),"total_tokens":sum(int(r.get("provider_result",{}).get("usage",{}).get("total_tokens",0) or 0) for r in records),"production_responses_changed":0,"retrieval_executions":0}
