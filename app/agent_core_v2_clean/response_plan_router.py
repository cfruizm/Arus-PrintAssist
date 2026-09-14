from __future__ import annotations
from .response_planner import build_response_plan,apply_plan_to_retrieval

def plan_turn(result,message):
    plan=build_response_plan(message,result.get("understanding") or {},result.get("retrieval") or {},result.get("evidence_decision") or {})
    result["canonical_response_plan"]=plan.to_dict();result["retrieval"]=apply_plan_to_retrieval(result.get("retrieval") or {},plan);return result,plan

def internal_assessment_from_plan(plan):
    mode=plan.response_plan["mode"];status="partial" if mode in {"hybrid","general_guidance_with_example"} else "insufficient"
    return {"status":status,"score":0.0,"reasons":["canonical_response_plan:"+mode],"generation_allowed":False,"internal_knowledge_candidate":True,"canonical_decision":{"status":status,"generation_mode":"documented_plus_internal" if mode=="hybrid" else "internal_only","reason":"canonical_response_plan","selected_ids":plan.evidence_plan["documented_ids"],"accepted":False}}
