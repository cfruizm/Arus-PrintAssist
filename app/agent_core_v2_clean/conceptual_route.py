from __future__ import annotations
from copy import deepcopy

CONCEPTUAL_INTENT = "conceptual"

def prepare_conceptual_retrieval(retrieval: dict, topic_relation: str) -> dict:
    """Create a generation view that cannot inherit answer context across a topic boundary."""
    clean = deepcopy(retrieval or {})
    if topic_relation == "new_topic":
        current = [
            deepcopy(item)
            for item in (clean.get("diagnostic_evidence") or clean.get("evidence") or [])
            if not item.get("carried_from_previous_answer")
        ]
        clean["generation_evidence"] = current[:8]
        clean["evidence"] = current[:8]
        clean["_answer_context"] = {}
        sf = clean.setdefault("semantic_fit", {})
        sf.update({
            "carried_previous_evidence": 0,
            "previous_answer_sources_used": False,
            "previous_evidence_primary_eligible": False,
            "previous_evidence_role": "none",
            "generation_ids": [x.get("id") for x in current[:8]],
            "generation_count": len(current[:8]),
        })
        clean["conceptual_boundary"] = {
            "isolated": True,
            "answer_context_removed": True,
            "current_evidence_count": len(current),
        }
    return clean

def conceptual_assessment(retrieval: dict) -> dict:
    evidence = retrieval.get("generation_evidence") or retrieval.get("evidence") or []
    return {
        "status": "partial" if evidence else "insufficient",
        "score": 0.0,
        "reasons": ["conceptual_answer_requires_controlled_synthesis"],
        "usable_chunks": len(evidence),
        "generation_allowed": False,
        "internal_knowledge_candidate": True,
        "canonical_decision": {
            "status": "partial" if evidence else "insufficient",
            "generation_mode": "documented_plus_internal" if evidence else "internal_only",
            "reason": "conceptual_controlled_synthesis",
            "selected_ids": [x.get("id") for x in evidence],
            "accepted": False,
        },
    }

def must_preempt_documented_answer(understanding: dict) -> bool:
    return (understanding or {}).get("intent") == CONCEPTUAL_INTENT
