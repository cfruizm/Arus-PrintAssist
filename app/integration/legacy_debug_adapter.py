from __future__ import annotations
from typing import Any
from app.agent_core.models import RetrievedDocument

def _source(metadata: dict) -> str:
    return str(metadata.get("canonical_url") or metadata.get("source_url") or metadata.get("source") or metadata.get("title") or "")

def diagnostics_to_documents(payload: dict[str, Any]) -> list[RetrievedDocument]:
    """Convert a read-only debug diagnostics payload to neutral documents.

    This adapter intentionally accepts several key names because the deployed
    debug payload must be inspected before finalizing the production contract.
    It never calls the LLM and never mutates session state.
    """
    candidate_lists = [
        payload.get("retrieved_docs"), payload.get("documents"), payload.get("results"),
        payload.get("ranked_docs"), payload.get("top_documents"),
    ]
    raw_items = next((items for items in candidate_lists if isinstance(items, list)), [])
    docs = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        metadata = dict(item.get("metadata") or {})
        for key in ("title", "source", "source_url", "canonical_url", "vendor", "product", "component"):
            if key in item and key not in metadata:
                metadata[key] = item[key]
        content = str(item.get("page_content") or item.get("content") or item.get("text") or "")
        score = float(item.get("score") or item.get("rerank_score") or 0.0)
        if content or _source(metadata):
            docs.append(RetrievedDocument(content, metadata, score))
    return docs

class LegacyDebugRetrievalAdapter:
    def __init__(self, diagnostics_callable):
        self._diagnostics_callable = diagnostics_callable

    def retrieve(self, query: str) -> tuple[list[RetrievedDocument], dict]:
        payload = self._diagnostics_callable(query)
        if not isinstance(payload, dict):
            raise TypeError("debug diagnostics must return a dict")
        return diagnostics_to_documents(payload), payload
