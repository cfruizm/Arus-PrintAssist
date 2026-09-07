from __future__ import annotations
import json

QUERY_SCHEMA = {
    "type":"object",
    "properties":{"query":{"type":"string"},"document_focus":{"type":"string"}},
    "required":["query","document_focus"]
}

def build_semantic_retry_query(gateway, original_query: str, contextual_query: str, state, retrieved_titles):
    from app.llm_gateway.models import LLMRequest
    payload = {
        "original_request": original_query,
        "current_contextual_query": contextual_query,
        "active_topic": state.active_topic.to_dict() if hasattr(state.active_topic, "to_dict") else {},
        "retrieved_titles_without_answer": list(retrieved_titles)[:6],
        "instruction": "Create one concise retrieval query that preserves the requested object and operation. Do not broaden to the whole product. document_focus is a short description of the passage that would directly answer the request."
    }
    result = gateway.complete(LLMRequest(
        [{"role":"system","content":"Generate a semantic retrieval retry. Do not answer the user. Return JSON only."},
         {"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],
        "agent_core_v2_retrieval_retry", 120, 0.0, QUERY_SCHEMA))
    if not result.ok:
        return None, {"used":True,"ok":False,"reason":"provider_error"}
    try:
        raw=json.loads(str(result.text).strip())
        query=str(raw.get("query") or "").strip()
        focus=str(raw.get("document_focus") or "").strip()
    except Exception:
        return None, {"used":True,"ok":False,"reason":"invalid_json"}
    if not query:
        return None, {"used":True,"ok":False,"reason":"empty_query"}
    return query, {"used":True,"ok":True,"reason":"insufficient_passage_coverage","document_focus":focus}

def merge_candidates(primary, retry, candidate_factory, max_candidates):
    merged=[]; seen=set()
    for item in list(primary or [])+list(retry or []):
        meta=dict(item.get("metadata") or {})
        key=str(meta.get("content_hash") or meta.get("canonical_url") or item.get("url") or meta.get("source_url") or (str(item.get("title"))+str(meta.get("page"))))
        if key in seen: continue
        seen.add(key); merged.append(item)
        if len(merged)>=max_candidates: break
    return [candidate_factory(item,i+1) for i,item in enumerate(merged)]
