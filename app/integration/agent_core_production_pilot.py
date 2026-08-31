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

GLOBAL_CANCEL_COMMANDS={"salir","cancelar","cancela","abortar","olvidar el caso","cancelar escalamiento","detener escalamiento"}
ACKNOWLEDGEMENTS={"ok","okay","gracias","listo","entendido","perfecto","de acuerdo"}
INDEPENDENT_ACTS={"ask_concept","request_procedure","request_support","request_next_step","ask_requirements","ask_architecture"}


def _norm(value):
    text=str(value or "").casefold().strip(" ¿?¡!.,:;")
    return " ".join(text.split())


def _clear_router_state(streamlit_state):
    removed=[]
    for key in list(streamlit_state.keys()):
        lowered=str(key).casefold()
        if any(token in lowered for token in ("router_shadow","agent_core_router","semantic_case_state","technical_case")):
            try:del streamlit_state[key];removed.append(key)
            except Exception:pass
    return removed


def reset_all_conversation_states(chat_session_state,streamlit_state):
    chat_session_state.mode="normal"
    chat_session_state.pending_incident_field=None
    chat_session_state.escalation_workflow_state="normal"
    chat_session_state.escalation_summary_ready=False
    chat_session_state.escalation_persisted=False
    if hasattr(chat_session_state,"incident_state"):
        incident=chat_session_state.incident_state
        for field,value in {
            "software_involved":None,"software_version":None,"actions_attempted":[],
            "error_description":None,"printer_data":None,"contract_client_location":None,
            "evidence":None,"impact_type":None,"escalation_requested":False,
        }.items():
            try:setattr(incident,field,value)
            except Exception:pass
    try:chat_session_state.conversation_topic={}
    except Exception:pass
    removed=_clear_router_state(streamlit_state)
    streamlit_state.pop("agent_core_semantic_real_chat_last_record",None)
    return removed


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


def _is_independent_question(user_message,model_decision,derived):
    text=str(user_message or "").strip()
    act=str(model_decision.get("conversation_act") or "")
    retrieval=model_decision.get("retrieval_request") or {}
    explicit_question=("?" in text or _norm(text).startswith(("que ","qué ","como ","cómo ","cual ","cuál ","necesito ","quiero ")))
    complete_retrieval=bool(retrieval.get("question") and (retrieval.get("problem_statement") or retrieval.get("products")))
    return bool(act in INDEPENDENT_ACTS or derived.get("requires_retrieval") or complete_retrieval or explicit_question)


def try_agent_core_production_pilot(user_message,chat_session_state,streamlit_state,secrets):
    started=time.perf_counter();normalized=_norm(user_message)
    record={"input":user_message,"status":"started","fallback_to_legacy":False,"answer_visible":False,"governor_version":"semantic_first_v1"}
    try:
        if normalized in GLOBAL_CANCEL_COMMANDS:
            removed=reset_all_conversation_states(chat_session_state,streamlit_state)
            answer="El escalamiento y el caso técnico activo fueron cancelados. Puedes continuar con una nueva consulta de soporte."
            record.update(status="served",answer_visible=True,route="global_cancel",answer=answer,cleared_router_keys=removed)
            return answer,record

        semantic=observe_semantic_real_chat_turn(user_message,chat_session_state,streamlit_state,secrets);record["semantic"]=semantic
        if semantic.get("status")!="ok":record.update(status="fallback",fallback_to_legacy=True,reason="semantic_unavailable");return None,record
        model_decision=semantic.get("model_decision") or {};normalized_decision=semantic.get("normalized_decision") or {};derived=semantic.get("derived_decision") or {}
        escalation_active=str(getattr(chat_session_state,"escalation_workflow_state","normal"))=="escalation_collecting"
        independent=_is_independent_question(user_message,model_decision,derived)
        record.update(escalation_active=escalation_active,independent_question=independent,conversation_act=model_decision.get("conversation_act"))

        if escalation_active and not independent:
            record.update(status="fallback",fallback_to_legacy=True,reason="continue_active_escalation");return None,record

        retrieval_request=(normalized_decision.get("retrieval_request") or model_decision.get("retrieval_request") or {})
        question=str(retrieval_request.get("question") or "").strip();problem=str(retrieval_request.get("problem_statement") or "").strip()
        explicit_request=bool(question and (problem or retrieval_request.get("products")))
        if not (derived.get("requires_retrieval") or explicit_request):
            record.update(status="fallback",fallback_to_legacy=True,reason="route_not_authorized_for_pilot");return None,record

        query=question or user_message
        if problem and problem.casefold() not in query.casefold():query=f"{problem}. {query}"
        retrieval=retrieve_from_existing_backend(query,6);record["retrieval"]=retrieval
        if not retrieval.get("ok"):record.update(status="fallback",fallback_to_legacy=True,reason="retrieval_failed");return None,record
        state=_temporary_case_state(chat_session_state,semantic);gateway=LLMGateway(load_gateway_config(secrets),streamlit_state)
        proposal=run_hybrid_response_lab(gateway,retrieval,query,state,str(derived.get("intent") or "troubleshooting"),str(secrets.get("LLM_INTERNAL_KNOWLEDGE_POLICY","hybrid_guarded")),max(250,min(500,int(secrets.get("LLM_ANSWER_MAX_TOKENS",400)))))
        record["proposal"]=proposal
        if not proposal.get("compliance",{}).get("compliant"):record.update(status="fallback",fallback_to_legacy=True,reason="proposal_non_compliant");return None,record
        answer=_clean_user_answer(proposal)
        if not answer:record.update(status="fallback",fallback_to_legacy=True,reason="empty_answer");return None,record
        record.update(status="served",answer_visible=True,route="independent_question" if escalation_active else "agent_core",provider=proposal.get("answer_result",{}).get("provider"),model=proposal.get("answer_result",{}).get("model"),response_mode=proposal.get("evidence_decision",{}).get("response_mode"),answer=answer,escalation_preserved_in_pause=escalation_active)
        return answer,record
    except Exception as exc:
        record.update(status="fallback",fallback_to_legacy=True,reason="pilot_exception",error=f"{type(exc).__name__}: {exc}");return None,record
    finally:
        record["latency_ms"]=round((time.perf_counter()-started)*1000,3)
        records=list(streamlit_state.get("agent_core_production_pilot_records",[]) or []);records.append(record);streamlit_state["agent_core_production_pilot_records"]=records[-100:];streamlit_state["agent_core_production_pilot_last_record"]=record
