from __future__ import annotations
import re
import time
from app.agent_core.conversation_act_runtime import compact_case_state
from app.agent_core.hybrid_response_lab import run_hybrid_response_lab
from app.integration.lab_retrieval_adapter import retrieve_from_existing_backend
from app.integration.semantic_real_chat_shadow import observe_semantic_real_chat_turn
from app.integration.session_adapter_v1 import get_or_create_router_shadow_state
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway


def _temporary_case_state(chat_session_state,semantic_record):
    router_state=get_or_create_router_shadow_state(chat_session_state)
    state=compact_case_state(router_state)
    state={key:(list(value) if isinstance(value,list) else value) for key,value in state.items()}
    decision=semantic_record.get("normalized_decision") or semantic_record.get("model_decision") or {}
    for update in decision.get("state_updates") or []:
        typ=str(update.get("type") or "");value=str(update.get("value") or "").strip()
        field={"product":"products","process":"processes","symptom":"symptoms","attempted_action":"attempted_actions"}.get(typ)
        if field and value:
            state.setdefault(field,[])
            if value not in state[field]:state[field].append(value)
        elif typ=="affected_scope" and value:state["affected_scope"]=value
        elif typ=="resolution_status" and value:state["resolution_status"]=value
    return state


def _clean_user_answer(proposal):
    answer=str(proposal.get("answer_result",{}).get("text") or "").strip()
    sources=proposal.get("evidence_selection",{}).get("selected_sources") or []
    used=set(re.findall(r"\[(S\d+)\]",answer))
    if not used:return answer
    answer=re.sub(r"\n+\*{0,2}Fuentes\*{0,2}\s*\n[\s\S]*$","",answer,flags=re.IGNORECASE).rstrip()
    lines=[]
    for source in sources:
        sid=str(source.get("id") or "")
        if sid not in used:continue
        title=str(source.get("title") or sid).strip();url=str(source.get("url") or "").strip()
        lines.append(f"- [{sid}] [{title}]({url})" if url.startswith("http") else f"- [{sid}] {title}")
    return answer+("\n\n### Fuentes\n"+"\n".join(lines) if lines else "")


def try_agent_core_production_pilot(user_message,chat_session_state,streamlit_state,secrets):
    started=time.perf_counter()
    record={"input":user_message,"status":"started","fallback_to_legacy":False,"answer_visible":False}
    try:
        semantic=observe_semantic_real_chat_turn(user_message,chat_session_state,streamlit_state,secrets)
        record["semantic"]=semantic
        if semantic.get("status")!="ok":
            record.update(status="fallback",fallback_to_legacy=True,reason="semantic_unavailable");return None,record
        model_decision=semantic.get("model_decision") or {};normalized=semantic.get("normalized_decision") or {};derived=semantic.get("derived_decision") or {}
        retrieval_request=(normalized.get("retrieval_request") or model_decision.get("retrieval_request") or {})
        question=str(retrieval_request.get("question") or "").strip();problem=str(retrieval_request.get("problem_statement") or "").strip()
        explicit_request=bool(question and (problem or retrieval_request.get("products")))
        if not (derived.get("requires_retrieval") or explicit_request):
            record.update(status="fallback",fallback_to_legacy=True,reason="route_not_authorized_for_pilot");return None,record
        query=question or user_message
        if problem and problem.casefold() not in query.casefold():query=f"{problem}. {query}"
        retrieval=retrieve_from_existing_backend(query,6);record["retrieval"]=retrieval
        if not retrieval.get("ok"):
            record.update(status="fallback",fallback_to_legacy=True,reason="retrieval_failed");return None,record
        state=_temporary_case_state(chat_session_state,semantic);gateway=LLMGateway(load_gateway_config(secrets),streamlit_state)
        proposal=run_hybrid_response_lab(gateway,retrieval,query,state,str(derived.get("intent") or "troubleshooting"),str(secrets.get("LLM_INTERNAL_KNOWLEDGE_POLICY","hybrid_guarded")),max(250,min(500,int(secrets.get("LLM_ANSWER_MAX_TOKENS",400)))))
        record["proposal"]=proposal
        if not proposal.get("compliance",{}).get("compliant"):
            record.update(status="fallback",fallback_to_legacy=True,reason="proposal_non_compliant");return None,record
        answer=_clean_user_answer(proposal)
        if not answer:
            record.update(status="fallback",fallback_to_legacy=True,reason="empty_answer");return None,record
        record.update(status="served",answer_visible=True,provider=proposal.get("answer_result",{}).get("provider"),model=proposal.get("answer_result",{}).get("model"),response_mode=proposal.get("evidence_decision",{}).get("response_mode"),answer=answer)
        return answer,record
    except Exception as exc:
        record.update(status="fallback",fallback_to_legacy=True,reason="pilot_exception",error=f"{type(exc).__name__}: {exc}");return None,record
    finally:
        record["latency_ms"]=round((time.perf_counter()-started)*1000,3)
        records=list(streamlit_state.get("agent_core_production_pilot_records",[]) or []);records.append(record);streamlit_state["agent_core_production_pilot_records"]=records[-100:];streamlit_state["agent_core_production_pilot_last_record"]=record
