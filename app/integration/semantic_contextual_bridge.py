from __future__ import annotations
from app.agent_core.conversation_act_runtime import compact_case_state
from app.agent_core.hybrid_response_lab import run_hybrid_response_lab
from app.integration.lab_retrieval_adapter import retrieve_from_existing_backend
from app.integration.session_adapter_v1 import get_or_create_router_shadow_state
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway

def try_semantic_contextual_bridge(user_message,chat_session_state,streamlit_state,secrets,semantic_record):
    record={"input":user_message,"status":"skipped","retrieval_executed":False,"answer_llm_called":False,"answer_visible":False}
    try:
        if not bool(secrets.get("AGENT_CORE_SEMANTIC_CONTEXTUAL_BRIDGE_ENABLED",False)): record["reason"]="disabled"; return None,record
        if not isinstance(semantic_record,dict) or semantic_record.get("status")!="ok": record["reason"]="semantic_unavailable"; return None,record
        decision=semantic_record.get("normalized_decision") or {}; derived=semantic_record.get("derived_decision") or {}
        if not derived.get("requires_retrieval"): record["reason"]="retrieval_not_required"; return None,record
        request=decision.get("retrieval_request") or {}; question=str(request.get("question") or user_message).strip(); problem=str(request.get("problem_statement") or "").strip(); query=question if not problem or problem.casefold() in question.casefold() else f"{problem}. {question}"
        retrieval=retrieve_from_existing_backend(query,6); record["retrieval"]=retrieval; record["retrieval_executed"]=bool(retrieval.get("ok"))
        if not retrieval.get("ok"): record.update(status="fallback",reason="retrieval_failed"); return None,record
        state=compact_case_state(get_or_create_router_shadow_state(chat_session_state)); gateway=LLMGateway(load_gateway_config(secrets),streamlit_state); proposal=run_hybrid_response_lab(gateway,retrieval,query,state,str(derived.get("intent") or "troubleshooting"),str(secrets.get("LLM_INTERNAL_KNOWLEDGE_POLICY","hybrid_guarded")),int(secrets.get("LLM_ANSWER_MAX_TOKENS",400))); record["proposal"]=proposal; provider=proposal.get("answer_result",{}).get("provider"); record["answer_llm_called"]=provider not in {None,"deterministic_policy"}
        answer=str(proposal.get("answer_result",{}).get("text") or "").strip()
        if not proposal.get("compliance",{}).get("compliant") or not answer:
            answer="El caso técnico sigue activo, pero la documentación consultada no permitió generar un siguiente paso suficientemente confiable. Conservo la validación ya realizada y puedes continuar con el escalamiento sin repetirla."
            record.update(status="served_guarded",reason="non_compliant_or_empty")
        else: record["status"]="served"
        record["answer_visible"]=True; record["answer"]=answer; streamlit_state["agent_core_semantic_contextual_last_record"]=record; return answer,record
    except Exception as exc:
        record.update(status="fallback",reason="bridge_exception",error=f"{type(exc).__name__}: {exc}"); streamlit_state["agent_core_semantic_contextual_last_record"]=record; return None,record
