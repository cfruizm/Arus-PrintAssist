from __future__ import annotations
import json
from .runtime_memory import compact_turn,compact_cache_artifact,enforce_runtime_memory_limits,memory_diagnostic

def evidence(i):
 return {"id":f"R{i}","title":"Long evidence","source":"doc://large","text":"x"*6000,"metadata":{"canonical_url":"doc://large","unused":"y"*2000},"semantic_fit":{"score":.5,"matched_terms":["queue"]}}

def run():
 turn={"input":"test","retrieval":{"diagnostic_evidence":[evidence(i) for i in range(12)],"generation_evidence":[evidence(i) for i in range(12)],"evidence":[evidence(i) for i in range(12)],"_answer_context":{"duplicate":"z"*10000}},"canonical_response_plan":{"schema_version":1,"evidence_plan":{"selected_evidence":[evidence(i) for i in range(8)]}},"answer_context":{"cited_evidence":[evidence(i) for i in range(10)],"active_document_evidence_ledger":[evidence(i) for i in range(10)],"main_text_excerpt":"q"*4000,"delivered_guidance":[]},"provider_trace":{"understanding":{"text":"p"*5000}}}
 compact=compact_turn(turn)
 store={"turns":[compact_turn(turn) for _ in range(12)],"messages":[{"role":"user","content":"x"} for _ in range(30)],"errors":[{} for _ in range(20)],"answer_context":compact["answer_context"]}
 for name in ("exact_turn_cache","retrieval_cache","documented_answer_cache","procedural_answer_cache","internal_knowledge_cache"):
  store[name]={str(i):{"artifact":compact_cache_artifact(turn)} for i in range(7)}
 enforce_runtime_memory_limits(store);diag=memory_diagnostic(store)
 checks={
  "evidence_bounded":len(compact["retrieval"]["diagnostic_evidence"])==6 and len(compact["retrieval"]["diagnostic_evidence"][0]["text"])==700,
  "duplicate_context_removed":"_answer_context" not in compact["retrieval"],
  "provider_trace_bounded":len(compact["provider_trace"]["understanding"]["text"])==900,
  "turns_bounded":len(store["turns"])==8,
  "messages_bounded":len(store["messages"])==18,
  "caches_bounded":all(x["entries"]==3 for x in diag["cache_summary"].values()),
  "diagnostic_available":diag["policy"]=="bounded_session_v1" and diag["estimated_store_bytes"]>0,
 }
 failed=[k for k,v in checks.items() if not v]
 return {"phase":"4B.3.7","status":"passed" if not failed else "failed","passed":len(checks)-len(failed),"failed":len(failed),"failed_checks":failed,"checks":checks,"estimated_store_bytes":diag["estimated_store_bytes"]}
if __name__=="__main__":
 r=run();print(json.dumps(r,indent=2));raise SystemExit(0 if r["status"]=="passed" else 1)
