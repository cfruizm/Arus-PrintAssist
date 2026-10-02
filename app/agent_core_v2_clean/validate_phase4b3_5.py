from __future__ import annotations
import json
from .unified_evidence_authority import apply_unified_evidence_verdict
from .semantic_fit import capture_answer_context
from .guidance_integrity import build_guidance_integrity_contract
from .semantic_contract import validate_response_contract


def ev(text, score=.2):
 return {"id":"R1","title":"General device maintenance","source":"doc://primary","page":"1","text":text,"semantic_fit":{"score":score},"metadata":{}}

def authority(evidence,status="partial",operation="diagnose retained queue"):
 prior={"goal":"diagnose retained queue","source_identities":["doc://primary"],"evidence_authority":{"status":status,"reason":"prior"}}
 retrieval={"query":{"fields":{"previous_evidence_role":"primary","topic_relation":"same_topic_refinement","user_act":"request_elaboration","goal":"diagnose retained queue","contextual_operation":operation,"details":{"operation":operation,"subject":"printer"}}},"diagnostic_evidence":[evidence],"_answer_context":prior}
 return apply_unified_evidence_verdict(retrieval,"Continue without repeating",{"intent":"troubleshooting","topic_relation":"same_topic","user_act":"request_elaboration","current_goal":"diagnose retained queue"})

def run():
 weak=authority(ev("Inspect the exterior, clean surfaces and record general equipment condition.",.18))
 strong=authority(ev("Inspect the retained print queue, identify the blocking job and validate the queue processing state.",.48),"sufficient")
 previous={"goal":"diagnose queue","source_identities":["doc://primary"],"active_document_evidence_ledger":[ev("Queue evidence",.5)],"delivered_guidance":[{"action":"Perform a complete functional test of the printer","semantic_signature":["complete","functional","printer","test"],"status":"delivered"}]}
 result={"answer":{"text":"### Next checks\n\n- Run a complete printer functional test.\n- Inspect the next documented condition.","mode":"controlled_internal_knowledge","finish_reason":"stop"},"retrieval":{"evidence":[]},"understanding":{"topic_relation":"same_topic","current_goal":"diagnose queue"},"document_continuity":{"same_topic":True,"primary":True}}
 context=capture_answer_context(result,previous); contract=build_guidance_integrity_contract({"_answer_context":context,"_case_context":{"attempts":[]}})
 reconciled=validate_response_contract("PaperCut MF remains the active product. Another optional field is not confirmed.",{"confirmed_facts":[{"key":"subject","value":"PaperCut MF"}],"unresolved_facts":[]})
 checks={
  "weak_primary_not_promoted":not bool((weak.get("evidence_verdict") or {}).get("reason")=="primary_document_operational_revalidation"),
  "strong_operational_primary_allowed":(strong.get("evidence_verdict") or {}).get("reason")=="primary_document_operational_revalidation",
  "fallback_preserves_document":context.get("source_identities")==["doc://primary"] and context.get("historical_document_context_preserved") is True,
  "heterogeneous_markdown_guidance_captured":len(context.get("delivered_guidance") or [])>=2,
  "semantic_duplicate_collapsed":sum("functional" in " ".join(x.get("semantic_signature") or []) for x in context.get("delivered_guidance") or [])==1,
  "remaining_only_policy_enabled":contract["response_policy"]["exclude_previous_guidance"] is True and contract["response_policy"]["repeat_full_instructions"] is False,
  "unrelated_denial_not_fact_contradiction":reconciled["valid"] is True,
 }
 failed=[k for k,v in checks.items() if not v]
 return {"phase":"4B.3.5","status":"passed" if not failed else "failed","passed":len(checks)-len(failed),"failed":len(failed),"failed_checks":failed,"checks":checks}

if __name__=="__main__":
 r=run();print(json.dumps(r,indent=2));raise SystemExit(0 if r["status"]=="passed" else 1)
