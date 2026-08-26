from __future__ import annotations
from dataclasses import asdict
from typing import Any

from app.integration.real_retrieval_bridge import RealRetrievalBridge
from app.retrieval.candidate_planner import build_candidate_queries


def source_key(doc) -> str:
    metadata = doc.metadata or {}
    return str(metadata.get("canonical_url") or metadata.get("source_url") or metadata.get("source") or metadata.get("title") or "")


def canonical_source(value: str) -> str:
    return str(value or "").split("#", 1)[0].rstrip("/")


def deduplicate_documents(documents: list) -> list:
    result, seen = [], set()
    for doc in documents:
        key = canonical_source(source_key(doc)) or (doc.page_content or "")[:160]
        if key in seen: continue
        seen.add(key); result.append(doc)
    return result


def summarize_documents(documents: list, limit: int = 8) -> list[dict[str, Any]]:
    summary = []
    for rank, doc in enumerate(documents[:limit], start=1):
        metadata = doc.metadata or {}
        summary.append({
            "rank": rank,
            "title": str(metadata.get("title") or ""),
            "source": source_key(doc),
            "vendor": metadata.get("vendor"),
            "product": metadata.get("product"),
            "component": metadata.get("component"),
            "source_type": metadata.get("source_type"),
            "score": doc.score,
            "content_preview": str(doc.page_content or "")[:300],
        })
    return summary


def evaluate_query(query: str, retrieve_context_callable, top_k: int = 6) -> dict:
    bridge = RealRetrievalBridge(retrieve_context_callable)
    legacy = bridge.retrieve(query, top_k=top_k)
    plan = build_candidate_queries(query)

    candidate_docs, planned_runs = [], []
    for planned_query in plan["queries"]:
        run = bridge.retrieve(planned_query, top_k=top_k)
        candidate_docs.extend(run["documents"])
        planned_runs.append({
            "query": planned_query,
            "latency_seconds": run["latency_seconds"],
            "document_count": len(run["documents"]),
        })
    candidate_docs = deduplicate_documents(candidate_docs)

    exact_source_respected = None
    if plan["exact_url"]:
        target = canonical_source(plan["exact_url"])
        candidate_docs = [doc for doc in candidate_docs if canonical_source(source_key(doc)) == target]
        exact_source_respected = all(canonical_source(source_key(doc)) == target for doc in candidate_docs)

    legacy_sources = [canonical_source(source_key(doc)) for doc in legacy["documents"] if source_key(doc)]
    candidate_sources = [canonical_source(source_key(doc)) for doc in candidate_docs if source_key(doc)]
    legacy_top3, candidate_top3 = set(legacy_sources[:3]), set(candidate_sources[:3])
    union = legacy_top3 | candidate_top3

    return {
        "query": query,
        "plan": plan,
        "legacy": {
            "latency_seconds": legacy["latency_seconds"],
            "context_chars": legacy["context_chars"],
            "documents": summarize_documents(legacy["documents"]),
        },
        "candidate": {
            "runs": planned_runs,
            "documents": summarize_documents(candidate_docs),
        },
        "metrics": {
            "top1_match": bool(legacy_sources and candidate_sources and legacy_sources[0] == candidate_sources[0]),
            "top3_overlap": round(len(legacy_top3 & candidate_top3) / max(1, len(union)), 4),
            "legacy_top3_count": len(legacy_top3),
            "candidate_top3_count": len(candidate_top3),
            "exact_source_respected": exact_source_respected,
        },
        "llm_calls": 0,
    }
