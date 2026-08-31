from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

@dataclass
class RetrievedEvidence:
    text: str
    title: str = ""
    source: str = ""
    url: str = ""
    score: float | None = None
    metadata: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _normalize_document(doc: Any) -> RetrievedEvidence:
    metadata = getattr(doc, "metadata", {}) or {}
    if not isinstance(metadata, dict):
        metadata = {}

    text = str(getattr(doc, "page_content", "") or "").strip()
    title = str(metadata.get("title") or metadata.get("name") or "").strip()
    source = str(
        metadata.get("source")
        or metadata.get("source_url")
        or metadata.get("canonical_url")
        or ""
    ).strip()
    url = str(
        metadata.get("source_url")
        or metadata.get("canonical_url")
        or metadata.get("url")
        or ""
    ).strip()

    raw_score = metadata.get("rerank_score")
    if raw_score is None:
        raw_score = metadata.get("score")
    try:
        score = None if raw_score is None else float(raw_score)
    except (TypeError, ValueError):
        score = None

    return RetrievedEvidence(
        text=text[:12000],
        title=title[:500],
        source=source[:2000],
        url=url[:2000],
        score=score,
        metadata=metadata,
    )


def retrieve_from_existing_backend(query: str, k: int = 6) -> dict:
    """Use PrintAssist's real retrieval pipeline without calling an LLM.

    backend.retrieve_context returns:
        (retrieved_context_text, retrieved_documents)

    Only retrieved_documents are converted into laboratory evidence.
    The function does not call generate_answer_with_rag and does not alter chat state.
    """
    try:
        from app.backend import retrieve_context
    except Exception as exc:
        return {
            "ok": False,
            "adapter": "app.backend.retrieve_context",
            "query": query,
            "evidence": [],
            "count": 0,
            "error_code": "retriever_import_failed",
            "errors": [f"{type(exc).__name__}: {exc}"],
        }

    try:
        raw_result = retrieve_context(query, top_k=max(1, min(10, int(k))))
    except Exception as exc:
        return {
            "ok": False,
            "adapter": "app.backend.retrieve_context",
            "query": query,
            "evidence": [],
            "count": 0,
            "error_code": "retrieval_execution_failed",
            "errors": [f"{type(exc).__name__}: {exc}"],
        }

    if not isinstance(raw_result, tuple) or len(raw_result) < 2:
        return {
            "ok": False,
            "adapter": "app.backend.retrieve_context",
            "query": query,
            "evidence": [],
            "count": 0,
            "error_code": "unexpected_retrieval_contract",
            "errors": [f"Expected tuple(context, docs), received {type(raw_result).__name__}"],
        }

    retrieved_context, retrieved_docs = raw_result[0], raw_result[1]
    docs = list(retrieved_docs or [])
    evidence = [
        _normalize_document(doc).to_dict()
        for doc in docs[: max(1, min(10, int(k)))]
        if str(getattr(doc, "page_content", "") or "").strip()
    ]

    return {
        "ok": True,
        "adapter": "app.backend.retrieve_context",
        "query": query,
        "evidence": evidence,
        "count": len(evidence),
        "retrieved_context_chars": len(str(retrieved_context or "")),
        "document_count_before_normalization": len(docs),
        "errors": [],
        "llm_called": False,
        "production_state_changed": False,
    }
