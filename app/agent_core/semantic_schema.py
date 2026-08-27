from __future__ import annotations
from app.agent_core.semantic_models import ALLOWED_ROUTES,ALLOWED_INTENTS,ALLOWED_UPDATE_TYPES,ALLOWED_NEXT_ACTIONS,SemanticCaseUpdate,RetrievalRequest,SemanticDecision

def _text(value,max_len=800): return str(value or "").strip()[:max_len]
def _confidence(value):
    try:return max(0.0,min(1.0,float(value)))
    except Exception:return 0.0

def validate_semantic_decision(data: dict)->SemanticDecision:
    if not isinstance(data,dict): raise ValueError("Semantic decision must be a JSON object")
    route=_text(data.get("route"),80)
    intent=_text(data.get("intent"),80)
    next_action=_text(data.get("next_action"),80)
    if route not in ALLOWED_ROUTES: raise ValueError(f"Unsupported route: {route}")
    if intent not in ALLOWED_INTENTS: raise ValueError(f"Unsupported intent: {intent}")
    if next_action not in ALLOWED_NEXT_ACTIONS: raise ValueError(f"Unsupported next_action: {next_action}")
    updates=[]
    for item in data.get("case_updates") or []:
        if not isinstance(item,dict):continue
        typ=_text(item.get("type"),80);value=_text(item.get("value"),1000)
        if typ not in ALLOWED_UPDATE_TYPES or not value:continue
        updates.append(SemanticCaseUpdate(typ,value,_confidence(item.get("confidence")),"current_user_message"))
    retrieval=None
    raw=data.get("retrieval_request")
    if isinstance(raw,dict):
        ri=_text(raw.get("intent"),80)
        if ri not in ALLOWED_INTENTS:ri=intent
        retrieval=RetrievalRequest(ri,[_text(x,120) for x in raw.get("products") or [] if _text(x,120)],[_text(x,120) for x in raw.get("processes") or [] if _text(x,120)],_text(raw.get("problem_statement"),1000) or None,_text(raw.get("question"),1000) or None,[_text(x,500) for x in raw.get("exclude_actions") or [] if _text(x,500)])
    requires_retrieval=bool(data.get("requires_retrieval"))
    if requires_retrieval and retrieval is None: raise ValueError("retrieval_request is required when requires_retrieval is true")
    if next_action=="retrieve" and not requires_retrieval: raise ValueError("retrieve action requires requires_retrieval=true")
    return SemanticDecision(route,intent,_confidence(data.get("confidence")),next_action,requires_retrieval,bool(data.get("requires_clarification")),bool(data.get("requires_escalation")),bool(data.get("topic_shift")),updates,[_text(x,200) for x in data.get("missing_information") or [] if _text(x,200)],_text(data.get("clarification_question"),600) or None,retrieval,_text(data.get("reasoning_summary"),600))
