from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterable

@dataclass(frozen=True)
class EvidenceBudget:
    max_sources: int
    max_partial: int
    max_total_chars: int
    max_chars_per_source: int

BUDGETS = {
    "conceptual": EvidenceBudget(3, 1, 8000, 2600),
    "requirements": EvidenceBudget(4, 1, 10000, 2800),
    "procedural": EvidenceBudget(5, 1, 13000, 3200),
    "troubleshooting": EvidenceBudget(5, 2, 12000, 3000),
    "architecture": EvidenceBudget(5, 2, 12000, 3000),
    "warranty": EvidenceBudget(4, 1, 9000, 2600),
    "default": EvidenceBudget(4, 1, 9000, 2600),
}

RANK = {"direct": 0, "conditional": 1, "partial": 2, "contextual": 3}

def _assessment(item: dict[str, Any]) -> dict[str, Any]:
    return item.get("semantic_assessment") or {}

def _applicability(item: dict[str, Any]) -> str:
    return str(_assessment(item).get("applicability") or item.get("applicability") or "contextual").lower()

def _source_key(item: dict[str, Any]) -> str:
    md = item.get("metadata") or {}
    return str(item.get("url") or md.get("canonical_url") or md.get("source_url") or md.get("source") or item.get("title") or item.get("id"))

def _claim_key(value: str) -> str:
    return " ".join(str(value or "").lower().split())[:240]

def select_evidence(evidence: dict[str, Any] | None, intent: str) -> dict[str, Any]:
    """Bound the evidence passed to the answer composer, without product-specific rules."""
    evidence = evidence or {}
    budget = BUDGETS.get(intent, BUDGETS["default"])
    candidates = list(evidence.get("citable") or evidence.get("retrieved") or [])
    candidates.sort(key=lambda x: (
        RANK.get(_applicability(x), 9),
        0 if (_assessment(x).get("subject_match") == "same") else 1,
        0 if (_assessment(x).get("task_match") == "same") else 1,
        -float(x.get("query_relevance_score") or x.get("retrieval_score") or 0),
    ))
    selected=[]; seen_sources=set(); seen_claims=set(); partial_count=0; total_chars=0
    for item in candidates:
        applicability=_applicability(item)
        if applicability == "partial" and partial_count >= budget.max_partial:
            continue
        source=_source_key(item)
        if source in seen_sources:
            continue
        assessment=_assessment(item)
        claims=[str(c).strip() for c in assessment.get("supported_claims", []) if str(c).strip()]
        fresh=[c for c in claims if _claim_key(c) not in seen_claims]
        text="\n".join(fresh) or str(item.get("text") or "")
        text=text[:budget.max_chars_per_source]
        if not text or total_chars + len(text) > budget.max_total_chars:
            continue
        compact=dict(item); compact["text"]=text
        compact["semantic_assessment"]={
            "applicability": applicability,
            "conditions": assessment.get("conditions") or [],
            "supported_claims": fresh or claims,
            "subject_match": assessment.get("subject_match"),
            "task_match": assessment.get("task_match"),
            "scope_relation": assessment.get("scope_relation"),
        }
        selected.append(compact); seen_sources.add(source); total_chars += len(text)
        for claim in fresh: seen_claims.add(_claim_key(claim))
        if applicability == "partial": partial_count += 1
        if len(selected) >= budget.max_sources: break
    ids=[str(x.get("id")) for x in selected if x.get("id")]
    return {"selected": selected, "selected_ids": ids, "source_count": len(selected), "total_chars": total_chars,
            "original_citable_count": len(candidates), "budget": budget.__dict__, "intent": intent}
