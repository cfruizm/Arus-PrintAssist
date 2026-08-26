from __future__ import annotations
import time
from typing import Any, Callable

from app.agent_core.models import RetrievedDocument


def convert_langchain_documents(items: list[Any]) -> list[RetrievedDocument]:
    converted = []
    for item in items or []:
        content = str(getattr(item, "page_content", "") or "")
        metadata = dict(getattr(item, "metadata", {}) or {})
        score = float(metadata.pop("_rerank_score", metadata.pop("_score", 0.0)) or 0.0)
        converted.append(RetrievedDocument(content, metadata, score))
    return converted


class RealRetrievalBridge:
    """Read-only bridge around the deployed retrieve_context function.

    The bridge never calls generate_answer_with_rag and therefore never calls
    the configured LLM. It only invokes the existing vector retrieval path.
    """

    def __init__(self, retrieve_context_callable: Callable):
        self._retrieve_context = retrieve_context_callable

    def retrieve(self, query: str, top_k: int = 6) -> dict:
        started = time.perf_counter()
        context, docs = self._retrieve_context(query, top_k=top_k)
        elapsed = time.perf_counter() - started
        converted = convert_langchain_documents(list(docs or []))
        return {
            "query": query,
            "documents": converted,
            "context_chars": len(str(context or "")),
            "latency_seconds": round(elapsed, 4),
            "llm_calls": 0,
        }
