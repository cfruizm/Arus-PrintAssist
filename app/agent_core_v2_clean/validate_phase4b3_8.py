from __future__ import annotations
import json
from pathlib import Path
from .runtime_memory import compact_cache_artifact,enforce_runtime_memory_limits,memory_diagnostic

def run():
 large={"answer":{"text":"answer","mode":"documented_answer"},"understanding":{"intent":"troubleshooting","current_goal":"diagnose"},"decision":{"action":"answer"},"retrieval":{"diagnostic_evidence":[{"text":"x"*10000}],"evidence_verdict":{"status":"sufficient","accepted":True,"reason":"exact_symptom_title_precedence","document_ids":["doc://one"]}},"answer_context":{"source_identities":["doc://one"],"active_document_evidence_ledger":[{"text":"y"*10000}]}}
 compact=compact_cache_artifact(large)
 store={"turns":[],"messages":[],"errors":[],"answer_context":{},"cache_metrics":{"configured_limits":{"exact_turn_cache":8,"retrieval_cache":8,"documented_answer_cache":8,"procedural_answer_cache":6,"internal_knowledge_cache":6}}}
 for name in ("exact_turn_cache","retrieval_cache","documented_answer_cache","procedural_answer_cache","internal_knowledge_cache"):
  store[name]={str(i):{"artifact":compact} for i in range(8)}
 enforce_runtime_memory_limits(store);diag=memory_diagnostic(store)
 prompt=Path(__file__).with_name("documented_answer.py").read_text(encoding="utf-8")
 checks={
  "exact_cache_one_entry":diag["cache_summary"]["exact_turn_cache"]["entries"]==1,
  "exact_cache_effective_limit_visible":diag["cache_summary"]["exact_turn_cache"]["effective_runtime_limit"]==1,
  "configured_and_effective_limits_separated":diag["cache_summary"]["exact_turn_cache"]["configured_limit"]==8,
  "cache_artifact_excludes_evidence_payload":"diagnostic_evidence" not in compact["retrieval"] and "active_document_evidence_ledger" not in compact["answer_context"],
  "conditional_applicability_instruction":"no la presentes como siguiente paso universal" in prompt and "si aplica" in prompt,
  "bounded_policy_v2":diag["policy"]=="bounded_session_v2",
 }
 failed=[k for k,v in checks.items() if not v]
 return {"phase":"4B.3.8","status":"passed" if not failed else "failed","passed":len(checks)-len(failed),"failed":len(failed),"failed_checks":failed,"checks":checks,"exact_cache_bytes":diag["cache_summary"]["exact_turn_cache"]["estimated_serialized_bytes"]}
if __name__=="__main__":
 r=run();print(json.dumps(r,indent=2));raise SystemExit(0 if r["status"]=="passed" else 1)
