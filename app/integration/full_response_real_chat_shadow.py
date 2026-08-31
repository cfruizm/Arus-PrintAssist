from __future__ import annotations
from datetime import datetime,timezone
import time
from app.agent_core.conversation_act_runtime import compact_case_state
from app.agent_core.hybrid_response_lab import run_hybrid_response_lab
from app.integration.lab_retrieval_adapter import retrieve_from_existing_backend
from app.integration.session_adapter_v1 import get_or_create_router_shadow_state
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway


def _latest_semantic_record(streamlit_state,user_message):
    records=list(streamlit_state.get("agent_core_semantic_real_chat_records",[]) or [])
    for record in reversed(records):
        if record.get("input")==user_message and record.get("status")=="ok":
            return record,records
    return None,records


def _temporary_case_state(chat_session_state,semantic_record):
    router_state=get_or_create_router_shadow_state(chat_session_state)
    state=compact_case_state(router_state)
    state={key:(list(value) if isinstance(value,list) else value) for key,value in state.items()}
    decision=(semantic_record or {}).get("normalized_decision") or (semantic_record or {}).get("model_decision") or {}
    for update in decision.get("state_updates") or []:
        typ=str(update.get("type") or "");value=str(update.get("value") or "").strip()
        if not value:continue
        mapping={"product":"products","process":"processes","symptom":"symptoms","attempted_action":"attempted_actions"}
        field=mapping.get(typ)
        if field:
            state.setdefault(field,[])
            if value not in state[field]:state[field].append(value)
        elif typ=="affected_scope":state["affected_scope"]=value
        elif typ=="resolution_status":state["resolution_status"]=value
        elif typ=="attempt_result" and value.casefold()=="failed":
            state.setdefault("failed_actions",[])
    return state


def observe_full_response_real_chat_shadow(user_message,production_answer,chat_session_state,streamlit_state,secrets):
    started=time.perf_counter();semantic_record,records=_latest_semantic_record(streamlit_state,user_message)
    base={"timestamp":datetime.now(timezone.utc).isoformat(),"input":user_message,"production_answer":production_answer,"production_response_changed":False,"retrieval_executed_by_shadow":False,"state_applied_to_production":False}
    if not semantic_record:
        shadow={**base,"status":"skipped","reason":"semantic_record_not_available"}
    else:
        derived=semantic_record.get("derived_decision") or {}
        normalized_decision=semantic_record.get("normalized_decision") or {}
        model_decision=semantic_record.get("model_decision") or {}
        decision=normalized_decision or model_decision
        case_state=_temporary_case_state(chat_session_state,semantic_record)

        # A structured model output can contain a complete retrieval request while
        # classifying the same turn as provide_case_detail. In full-response shadow
        # mode, recover that explicit request instead of discarding it. This does not
        # change the productive route or the persisted productive state.
        raw_retrieval_request=model_decision.get("retrieval_request") or {}
        normalized_retrieval_request=normalized_decision.get("retrieval_request") or {}
        retrieval_request=normalized_retrieval_request or raw_retrieval_request
        request_question=str(retrieval_request.get("question") or "").strip()
        request_problem=str(retrieval_request.get("problem_statement") or "").strip()
        recovery_applied=bool(
            not derived.get("requires_retrieval")
            and request_question
            and (request_problem or retrieval_request.get("products"))
        )
        should_retrieve=bool(derived.get("requires_retrieval") or recovery_applied)

        if not should_retrieve:
            shadow={**base,"status":"skipped","reason":"semantic_decision_does_not_require_retrieval","semantic_decision":decision,"model_decision":model_decision,"derived_decision":derived,"case_state":case_state,"retrieval_recovery_applied":False}
        else:
            query=str(request_question or user_message).strip()
            problem=str(request_problem or "").strip()
            if problem and problem.casefold() not in query.casefold():query=f"{problem}. {query}"
            retrieval=retrieve_from_existing_backend(query,6);base["retrieval_executed_by_shadow"]=True
            if not retrieval.get("ok"):
                shadow={**base,"status":"retrieval_error","semantic_decision":decision,"model_decision":model_decision,"derived_decision":derived,"case_state":case_state,"retrieval":retrieval,"retrieval_recovery_applied":recovery_applied}
            else:
                config=load_gateway_config(secrets);gateway=LLMGateway(config,streamlit_state);intent=str(derived.get("intent") or "troubleshooting");policy=str(secrets.get("LLM_INTERNAL_KNOWLEDGE_POLICY","hybrid_guarded"));max_tokens=max(250,min(500,int(secrets.get("LLM_ANSWER_MAX_TOKENS",400))))
                proposal=run_hybrid_response_lab(gateway,retrieval,query,case_state,intent,policy,max_tokens)
                shadow={**base,"status":"ok","semantic_decision":decision,"model_decision":model_decision,"derived_decision":derived,"case_state":case_state,"query_used":query,"proposal":proposal,"proposed_answer":proposal.get("answer_result",{}).get("text",""),"retrieval_recovery_applied":recovery_applied,"retrieval_recovery_reason":"explicit_model_retrieval_request" if recovery_applied else None}
    shadow["total_shadow_latency_ms"]=round((time.perf_counter()-started)*1000,3)
    if semantic_record is not None:
        semantic_record["full_response_shadow"]=shadow
        streamlit_state["agent_core_semantic_real_chat_records"]=records[-100:]
        streamlit_state["agent_core_semantic_real_chat_last_record"]=semantic_record
    streamlit_state["agent_core_full_response_shadow_last_record"]=shadow
    full=list(streamlit_state.get("agent_core_full_response_shadow_records",[]) or []);full.append(shadow);streamlit_state["agent_core_full_response_shadow_records"]=full[-100:]
    return shadow
