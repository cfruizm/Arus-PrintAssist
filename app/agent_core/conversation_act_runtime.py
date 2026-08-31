from __future__ import annotations
import copy

UPDATE_TO_STATE_FIELD={
    "product":"products","process":"processes","symptom":"symptoms",
    "attempted_action":"attempted_actions","affected_scope":"affected_scope",
    "resolution_status":"resolution_status"
}

def compact_case_state(router_state)->dict:
    topic=getattr(router_state,"topic",None);case=getattr(router_state,"technical_case",None)
    return {
        "status":getattr(case,"status","idle"),
        "products":list(getattr(topic,"products",[]) or []),
        "processes":list(getattr(topic,"processes",[]) or []),
        "symptoms":list(getattr(case,"symptoms",[]) or []),
        "attempted_actions":list(getattr(case,"attempted_actions",[]) or []),
        "failed_actions":list(getattr(case,"failed_actions",[]) or []),
        "affected_scope":getattr(case,"affected_users",None),
        "resolution_status":getattr(case,"resolution_status",None),
    }

def _norm(value):return " ".join(str(value or "").casefold().split())

def sanitize_semantic_decision(model_decision:dict,derived_decision:dict,case_state:dict)->dict:
    normalized=copy.deepcopy(model_decision);sanitized=[];deduplicated=[]
    mode=str(derived_decision.get("response_mode") or normalized.get("response_mode") or "")
    if mode!="retrieve" and normalized.get("retrieval_request") is not None:
        normalized["retrieval_request"]=None;sanitized.append("retrieval_request")
    if mode!="clarification" and normalized.get("conversation_act") not in {"request_support"} and normalized.get("clarification_question"):
        normalized["clarification_question"]=None;sanitized.append("clarification_question")
    existing={
        "product":case_state.get("products",[]),"process":case_state.get("processes",[]),
        "symptom":case_state.get("symptoms",[]),"attempted_action":case_state.get("attempted_actions",[]),
        "affected_scope":[case_state.get("affected_scope")],"resolution_status":[case_state.get("resolution_status")],
        "attempt_result":["failed"] if case_state.get("failed_actions") or case_state.get("resolution_status")=="unresolved" else []
    }
    clean=[]
    for update in normalized.get("state_updates") or []:
        typ=str(update.get("type") or "");value=update.get("value")
        if any(_norm(value)==_norm(item) for item in existing.get(typ,[]) if item is not None):
            deduplicated.append({"type":typ,"value":value});continue
        clean.append(update)
    normalized["state_updates"]=clean
    return {"normalized_decision":normalized,"fields_sanitized":sanitized,"updates_deduplicated":deduplicated,"normalization_applied":bool(sanitized or deduplicated)}
