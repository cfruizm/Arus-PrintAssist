from __future__ import annotations
from dataclasses import dataclass,asdict
from copy import deepcopy
from .entity_scope import normalize_scope
from .citation_registry import citation_plan

@dataclass(frozen=True)
class ResponsePlan:
    schema_version:int
    request:dict
    evidence_plan:dict
    response_plan:dict
    def to_dict(self):return asdict(self)

def _operation(u):
    updates=u.get("goal_updates") or {}
    return updates.get("operation") or u.get("current_goal") or ""
def _subject(u):
    updates=u.get("goal_updates") or {}
    return updates.get("subject") or u.get("current_goal") or ""
def _missing(intent,scope):
    if intent!="procedural":return []
    missing=[]
    if not (scope.manufacturer or scope.model or scope.product):missing.append("manufacturer_or_model")
    if not scope.operating_system:missing.append("operating_system")
    return missing

def build_response_plan(message,understanding,retrieval,evidence_decision=None):
    u=understanding or {};scope=normalize_scope(u.get("goal_updates") or {});intent=str(u.get("intent") or "unknown");missing=_missing(intent,scope)
    evidence=list((retrieval or {}).get("generation_evidence") or (retrieval or {}).get("evidence") or [])
    guard=(retrieval or {}).get("procedural_scope_guard") or {};decision=evidence_decision or {}
    documented=bool(evidence) and not guard.get("restricted_to_example") and decision.get("status")!="insufficient"
    example=bool(evidence) and guard.get("restricted_to_example")
    citations=citation_plan(evidence if documented else [])
    if documented:mode="documented" if decision.get("status")=="sufficient" else "hybrid"
    elif example:mode="general_guidance_with_example"
    else:mode="internal"
    request={"intent":intent,"operation":_operation(u),"subject":_subject(u),"scope":scope.to_dict(),"missing_material_details":missing,"message":message}
    evidence_plan={"status":decision.get("status") or ("partial" if example else "insufficient"),"mode":mode,"documented_ids":citations["valid_ids"],"example_ids":[str(x.get("id")) for x in evidence[:1]] if example else [],"citation_map":citations["citation_map"],"selected_evidence":citations["selected_evidence"],"rejected":{"scope_mismatch":[str(x.get("id")) for x in evidence] if example else [],"carried_context":[],"duplicate":[]}}
    response={"mode":mode,"must_answer_general":not documented,"must_ask_one_detail":bool(missing),"question_target":missing[0] if missing else None,"allow_documented_claims":documented,"allow_internal_guidance":not documented or mode=="hybrid","allow_example_claims":example,"complete_goal":documented and not missing}
    return ResponsePlan(1,request,evidence_plan,response)

def apply_plan_to_retrieval(retrieval,plan):
    out=deepcopy(retrieval or {});ep=plan.evidence_plan;out["response_plan"]=plan.to_dict()
    if ep["mode"] in {"documented","hybrid"}:out["generation_evidence"]=deepcopy(ep["selected_evidence"]);out["evidence"]=deepcopy(ep["selected_evidence"])
    elif ep["mode"]=="general_guidance_with_example":out["generation_evidence"]=[];out["evidence"]=[]
    else:out["generation_evidence"]=[];out["evidence"]=[]
    return out
