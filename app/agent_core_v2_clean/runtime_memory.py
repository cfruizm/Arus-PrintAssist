from __future__ import annotations
from copy import deepcopy
import json

MAX_RETAINED_TURNS=8
MAX_RETAINED_MESSAGES=18
MAX_ERRORS=12
MAX_CACHE_ENTRIES=3
MAX_EVIDENCE_ITEMS=6
MAX_EVIDENCE_TEXT=700
MAX_EXCERPT=900


def _json_bytes(value):
    try:return len(json.dumps(value,ensure_ascii=False,separators=(",",":")).encode("utf-8"))
    except Exception:return 0


def _compact_evidence(item):
    row={k:deepcopy(item.get(k)) for k in ("id","title","source","url","page","origin","stable_id") if item.get(k) not in (None,"")}
    text=" ".join(str(item.get("text") or "").split())
    if text:row["text"]=text[:MAX_EVIDENCE_TEXT]
    if item.get("semantic_fit"):row["semantic_fit"]={k:deepcopy(item["semantic_fit"].get(k)) for k in ("score","matched_terms","title_matched_terms","concept_matches") if item["semantic_fit"].get(k) not in (None,[],{})}
    metadata=item.get("metadata") or {}
    row["metadata"]={k:deepcopy(metadata.get(k)) for k in ("canonical_url","source_url","product","vendor","source_type","document_family","title") if metadata.get(k) not in (None,"")}
    return row


def _compact_retrieval(value):
    r=deepcopy(value or {})
    arrays=("diagnostic_evidence","generation_evidence","evidence")
    for key in arrays:
        if key in r:r[key]=[_compact_evidence(x) for x in (r.get(key) or [])[:MAX_EVIDENCE_ITEMS]]
    verdict=r.get("evidence_verdict") or {}
    if verdict.get("selected_evidence") is not None:
        verdict["selected_evidence"]=[_compact_evidence(x) for x in (verdict.get("selected_evidence") or [])[:MAX_EVIDENCE_ITEMS]]
    r["evidence_verdict"]=verdict
    # Internal context is already exported independently and otherwise duplicates evidence.
    r.pop("_answer_context",None);r.pop("_case_context",None)
    return r


def _compact_answer_context(value):
    c=deepcopy(value or {})
    for key in ("cited_evidence","current_answer_cited_evidence","active_document_evidence_ledger"):
        if key in c:c[key]=[_compact_evidence(x) for x in (c.get(key) or [])[:MAX_EVIDENCE_ITEMS]]
    if c.get("main_text_excerpt"):c["main_text_excerpt"]=" ".join(str(c["main_text_excerpt"]).split())[:MAX_EXCERPT]
    c["delivered_guidance"]=[deepcopy(x) for x in (c.get("delivered_guidance") or [])[-10:]]
    return c


def compact_turn(result):
    out=deepcopy(result or {})
    if "retrieval" in out:out["retrieval"]=_compact_retrieval(out.get("retrieval"))
    if "answer_context" in out:out["answer_context"]=_compact_answer_context(out.get("answer_context"))
    plan=out.get("canonical_response_plan") or {}
    if plan:
        out["canonical_response_plan"]={k:deepcopy(plan.get(k)) for k in ("schema_version","response_plan","evidence_plan","diagnostic_plan","validation") if plan.get(k) is not None}
        ep=out["canonical_response_plan"].get("evidence_plan") or {}
        ep.pop("selected_evidence",None)
    trace=out.get("provider_trace") or {}
    for value in trace.values():
        if isinstance(value,dict) and len(str(value.get("text") or ""))>MAX_EXCERPT:value["text"]=str(value["text"])[:MAX_EXCERPT]
    out["provider_trace"]=trace
    out["runtime_compaction"]={"policy":"bounded_session_v1","serialized_bytes":_json_bytes(out)}
    return out


def compact_cache_artifact(artifact):
    out=deepcopy(artifact or {})
    if "retrieval" in out:out["retrieval"]=_compact_retrieval(out.get("retrieval"))
    if "answer_context" in out:out["answer_context"]=_compact_answer_context(out.get("answer_context"))
    return out


def _trim_cache(cache,limit=MAX_CACHE_ENTRIES):
    if not isinstance(cache,dict):return
    while len(cache)>limit:
        cache.pop(next(iter(cache)),None)


def enforce_runtime_memory_limits(store):
    store["turns"]=(store.get("turns") or [])[-MAX_RETAINED_TURNS:]
    store["messages"]=(store.get("messages") or [])[-MAX_RETAINED_MESSAGES:]
    store["errors"]=(store.get("errors") or [])[-MAX_ERRORS:]
    for name in ("exact_turn_cache","retrieval_cache","documented_answer_cache","procedural_answer_cache","internal_knowledge_cache"):
        _trim_cache(store.setdefault(name,{}))
    store["runtime_memory_diagnostic"]=memory_diagnostic(store)
    return store


def memory_diagnostic(store):
    turns=store.get("turns") or []
    caches={name:{"entries":len(store.get(name) or {}),"estimated_serialized_bytes":_json_bytes(store.get(name) or {})} for name in ("exact_turn_cache","retrieval_cache","documented_answer_cache","procedural_answer_cache","internal_knowledge_cache")}
    return {"policy":"bounded_session_v1","retained_turns":len(turns),"retained_messages":len(store.get("messages") or []),"turn_bytes":_json_bytes(turns),"answer_context_bytes":_json_bytes(store.get("answer_context") or {}),"cache_summary":caches,"estimated_store_bytes":_json_bytes({k:v for k,v in store.items() if k!="memory"})}
