from __future__ import annotations
from copy import deepcopy
import re
import unicodedata

CONCEPTUAL_INTENT = "conceptual"
_GENERIC = {"concept", "concepto", "explicar", "explica", "definir", "definicion", "relacion", "relaciona", "entre", "cuales", "existen", "existentes", "principales", "impresion", "printing", "operation", "subject", "de", "del", "la", "el", "los", "las", "que", "como", "con", "ese", "esta", "este", "print", "printer", "impresora", "software", "sistema", "dispositivo"}

def _tokens(value):
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii").casefold()
    return {x for x in re.findall(r"[a-z0-9]+", text) if len(x) > 2 and x not in _GENERIC}

def _concept_anchors(understanding):
    understanding = understanding or {}
    updates = understanding.get("goal_updates") or {}
    return _tokens(updates.get("subject")) or _tokens(understanding.get("current_goal"))

def _direct_current_evidence(items, understanding):
    subject = _concept_anchors(understanding)
    selected = []
    for item in items or []:
        if item.get("carried_from_previous_answer"):
            continue
        fit = item.get("semantic_fit") or {}
        body = " ".join((str(item.get("title") or ""), str(item.get("text") or ""), " ".join(map(str, fit.get("matched_terms") or []))))
        if subject and subject.intersection(_tokens(body)):
            selected.append(deepcopy(item))
    return selected[:8]

def _context_without_citation_authority(context):
    context = deepcopy(context or {})
    if not context:
        return {}
    for key in ("source_identities", "source_titles", "cited_ids", "cited_evidence"):
        context[key] = []
    context["citation_eligible"] = False
    context["role"] = "semantic_continuity_only"
    return context

def prepare_conceptual_retrieval(retrieval: dict, boundary, understanding: dict | None = None) -> dict:
    """Separate semantic continuity from documentary authority."""
    clean = deepcopy(retrieval or {})
    if isinstance(boundary, str):
        boundary = {"relation": boundary, "changed_dimensions": []}
    boundary = boundary or {}
    changed = set(boundary.get("changed_dimensions") or [])
    new_topic = boundary.get("relation") == "new_topic"
    subject_shift = "subject" in changed
    candidates = clean.get("diagnostic_evidence") or clean.get("evidence") or []
    current = (_direct_current_evidence(candidates, understanding) if understanding is not None else [deepcopy(x) for x in candidates if not x.get("carried_from_previous_answer")][:8])
    previous_context = clean.get("_answer_context") or {}
    current_anchors = _concept_anchors(understanding)
    previous_anchors = _tokens(previous_context.get("goal"))
    inferred_subject_shift = bool(previous_anchors and current_anchors and current_anchors != previous_anchors)
    subject_shift = subject_shift or inferred_subject_shift
    if new_topic:
        clean["_answer_context"] = {}
        context_role = "none"
    elif subject_shift:
        clean["_answer_context"] = _context_without_citation_authority(previous_context)
        context_role = "semantic_continuity_only"
    else:
        context_role = "eligible"
    clean["generation_evidence"] = current
    clean["evidence"] = current
    sf = clean.setdefault("semantic_fit", {})
    sf.update({"carried_previous_evidence": 0, "previous_answer_sources_used": False, "previous_evidence_primary_eligible": False if (new_topic or subject_shift) else sf.get("previous_evidence_primary_eligible", False), "previous_evidence_role": context_role, "generation_ids": [x.get("id") for x in current], "generation_count": len(current), "accepted_for_generation": bool(current), "low_fit": not bool(current)})
    clean["conceptual_boundary"] = {"isolated": new_topic, "answer_context_removed": new_topic, "subject_scope_changed": subject_shift, "subject_shift_inferred": inferred_subject_shift, "current_concept_anchors": sorted(current_anchors), "previous_concept_anchors": sorted(previous_anchors), "conversation_context_preserved": bool(subject_shift and previous_context), "previous_context_citation_eligible": not (new_topic or subject_shift), "direct_evidence_count": len(current), "dropped_tangential_count": max(0, len(candidates) - len(current))}
    return clean

def conceptual_assessment(retrieval: dict) -> dict:
    evidence = retrieval.get("generation_evidence") or []
    documented = bool(evidence)
    return {"status": "partial" if documented else "insufficient", "score": 0.0, "reasons": ["conceptual_answer_requires_controlled_synthesis", *([] if documented else ["no_direct_conceptual_evidence"])], "usable_chunks": len(evidence), "generation_allowed": False, "internal_knowledge_candidate": True, "canonical_decision": {"status": "partial" if documented else "insufficient", "generation_mode": "documented_plus_internal" if documented else "internal_only", "reason": "conceptual_controlled_synthesis", "selected_ids": [x.get("id") for x in evidence], "accepted": False}}

def must_preempt_documented_answer(understanding: dict) -> bool:
    return (understanding or {}).get("intent") == CONCEPTUAL_INTENT
