from __future__ import annotations
from app.agent_core.router_models import ContextFact, RouterShadowState

ALLOWED_UPDATE_TYPES={"product","process","symptom","attempted_action","attempt_result","affected_scope","error_message","evidence","technical_context","resolution_status"}
RESOLVED_VALUES={"resolved","successful","success","solved","resuelto","exitoso"}
FAILED_VALUES={"failed","failure","unresolved","fallido","no_resuelto"}

def _norm(value): return " ".join(str(value or "").casefold().split())
def _contains(values,candidate): return bool(_norm(candidate)) and any(_norm(v)==_norm(candidate) for v in values)
def _fact_exists(facts,typ,value): return any(_norm(getattr(f,"fact_type",""))==_norm(typ) and _norm(getattr(f,"value",""))==_norm(value) for f in facts)
def _append_fact(case,typ,value,confidence):
    if _fact_exists(case.context_facts,typ,value): return False
    case.context_facts.append(ContextFact(fact_type=typ,value=value,confidence=confidence,source="semantic_orchestrator",metadata={"application_mode":"controlled_state_update"}))
    return True

def _event(update,status,reason=None):
    result={"type":str(update.get("type") or ""),"value":str(update.get("value") or ""),"confidence":float(update.get("confidence") or 0.0),"status":status}
    if reason: result["reason"]=reason
    return result

def apply_semantic_state_updates(router_state:RouterShadowState,normalized_decision:dict,*,minimum_confidence:float=0.75)->dict:
    report={"attempted":0,"applied":[],"skipped":[],"changed":False,"minimum_confidence":minimum_confidence}
    if not isinstance(normalized_decision,dict):
        report["skipped"].append({"status":"skipped","reason":"decision_not_object"}); return report
    if normalized_decision.get("topic_shift"):
        report["skipped"].append({"status":"skipped","reason":"topic_shift_not_applied_in_this_stage"})
    topic=router_state.topic; case=router_state.technical_case
    for raw in normalized_decision.get("state_updates") or []:
        report["attempted"]+=1
        if not isinstance(raw,dict): report["skipped"].append({"status":"skipped","reason":"update_not_object"}); continue
        update=dict(raw); typ=str(update.get("type") or "").strip(); value=str(update.get("value") or "").strip()[:400]
        try: confidence=max(0.0,min(1.0,float(update.get("confidence",0.0))))
        except Exception: confidence=0.0
        update["confidence"]=confidence
        if typ not in ALLOWED_UPDATE_TYPES: report["skipped"].append(_event(update,"skipped","unsupported_type")); continue
        if not value: report["skipped"].append(_event(update,"skipped","empty_value")); continue
        if confidence<minimum_confidence: report["skipped"].append(_event(update,"skipped","below_confidence_threshold")); continue
        applied=False
        if typ=="product":
            if not _contains(topic.products,value): topic.products.append(value); applied=True
        elif typ=="process":
            if not _contains(topic.processes,value): topic.processes.append(value); applied=True
        elif typ=="symptom":
            if not _contains(case.symptoms,value): case.symptoms.append(value); applied=True
            if case.status in {"idle","intake"}: case.status="diagnosing"
        elif typ=="attempted_action":
            if not _contains(case.attempted_actions,value): case.attempted_actions.append(value); applied=True
        elif typ=="attempt_result":
            nv=_norm(value)
            if nv in FAILED_VALUES:
                case.resolution_status="unresolved"
                if case.status not in {"resolved","completed"}: case.status="unresolved"
                if case.attempted_actions and not _contains(case.failed_actions,case.attempted_actions[-1]): case.failed_actions.append(case.attempted_actions[-1]); applied=True
                applied=_append_fact(case,"attempt_result","failed",confidence) or applied
            elif nv in RESOLVED_VALUES:
                case.resolution_status="resolved"; case.status="resolved"; applied=_append_fact(case,"attempt_result","successful",confidence)
            else: applied=_append_fact(case,"attempt_result",value,confidence)
        elif typ=="affected_scope":
            if _norm(case.affected_users)!=_norm(value): case.affected_users=value; applied=True
        elif typ=="resolution_status":
            nv=_norm(value); canonical="resolved" if nv in RESOLVED_VALUES else ("unresolved" if nv in FAILED_VALUES else value)
            if _norm(case.resolution_status)!=_norm(canonical):
                case.resolution_status=canonical
                if canonical in {"resolved","unresolved"}: case.status=canonical
                applied=True
        elif typ=="evidence":
            if not _contains(case.evidence,value): case.evidence.append(value); applied=True
        else: applied=_append_fact(case,typ,value,confidence)
        if applied: report["applied"].append(_event(update,"applied")); report["changed"]=True
        else: report["skipped"].append(_event(update,"skipped","duplicate_or_no_change"))
    router_state.conversation.last_user_act=str(normalized_decision.get("conversation_act") or "") or None
    return report
