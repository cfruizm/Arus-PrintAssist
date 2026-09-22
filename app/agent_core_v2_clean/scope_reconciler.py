from __future__ import annotations

import re
import unicodedata
from .topic_boundary import infer_topic_boundary

_TOKEN_RE = re.compile(r"[\wáéíóúüñ]+", re.I)
_GENERIC = {
    "ahora", "dame", "unicamente", "solamente", "resume", "explica", "explicame",
    "procedimiento", "documentado", "metodo", "metodos", "validar", "antes", "iniciar",
    "que", "debo", "para", "por", "del", "una", "uno", "the", "only", "method",
    "procedure", "before", "start", "update", "actualizar", "actualizacion",
}
_REFERENTIAL_ACTS = {
    "request_elaboration", "follow_up", "answer", "answer_to_question", "continue",
    "verification", "request_details",
}
_CONTINUATION_INTENTS = {"procedural", "requirements", "verification", "conceptual"}


def _norm(value):
    return unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold()


def _safe_text(value):
    if value is None:return ""
    if isinstance(value,str):return value
    if isinstance(value,(int,float,bool)):return str(value)
    if isinstance(value,dict):return " ".join(_safe_text(v) for v in value.values() if _safe_text(v))
    if isinstance(value,(list,tuple,set)):return " ".join(_safe_text(v) for v in value if _safe_text(v))
    return str(value)

def _tokens(value):
    return {x for x in _TOKEN_RE.findall(_norm(value)) if len(x) > 2 and x not in _GENERIC}


def _semantic_continuation(understanding, memory):
    """Detect a focused follow-up within the same operational subject.

    This is intentionally domain-independent. It compares the previous active objective, the
    current structured goal and the current subject/operation. A change of method is treated as
    refinement when the underlying object/operation family remains shared.
    """
    previous = " ".join(
        _safe_text(x) for x in [
            getattr(memory, "active_topic", None),
            getattr(getattr(memory, "pending_goal", None), "summary", None),
            (getattr(getattr(memory, "pending_goal", None), "known_details", {}) or {}).get("subject"),
            (getattr(getattr(memory, "pending_goal", None), "known_details", {}) or {}).get("operation"),
        ] if _safe_text(x)
    )
    current_details = dict(getattr(understanding, "goal_updates", {}) or {})
    current = " ".join(
        _safe_text(x) for x in [
            getattr(understanding, "current_goal", None),
            current_details.get("subject"),
            current_details.get("operation"),
            current_details.get("method"),
            current_details.get("focus"),
        ] if _safe_text(x)
    )
    old = _tokens(previous)
    new = _tokens(current)
    if not old or not new:
        return False, 0.0
    shared = old & new
    ratio = len(shared) / max(1, min(len(old), len(new)))
    # Two meaningful shared terms, or one highly discriminative shared term in a referential turn.
    referential = str(getattr(understanding, "user_act", "") or "").casefold() in _REFERENTIAL_ACTS
    same_family = len(shared) >= 2 or (referential and ratio >= 0.20 and len(shared) >= 1)
    return same_family, round(ratio, 3)


def reconcile_turn(understanding, memory, message):
    corrections = []
    before = memory.to_dict() if hasattr(memory, "to_dict") else {}
    boundary = infer_topic_boundary(before, understanding.to_dict())
    case = getattr(memory, "support_case", None)
    case_active = bool(case and case.status in {"diagnosing", "reopened"})

    active_case_continuation = (
        case_active
        and understanding.intent in {"troubleshooting", "procedural", "requirements", "verification"}
        and understanding.domain_relevance == "in_scope"
    )
    semantic_followup, semantic_ratio = _semantic_continuation(understanding, memory)
    completed_goal_followup = (
        semantic_followup
        and understanding.intent in _CONTINUATION_INTENTS
        and understanding.domain_relevance == "in_scope"
    )

    if active_case_continuation:
        understanding.topic_relation = "same_topic"
        boundary = type(boundary)(
            "same_topic_refinement", "active_case_continuity", boundary.shared_ratio,
            boundary.changed_dimensions, boundary.introduced_dimensions, "primary"
        )
        corrections.append("active_case_continuity_preserved")
    elif completed_goal_followup:
        understanding.topic_relation = "same_topic"
        if understanding.user_act == "new_request":
            understanding.user_act = "request_elaboration"
        boundary = type(boundary)(
            "same_topic_refinement", "semantic_goal_followup", semantic_ratio,
            boundary.changed_dimensions, boundary.introduced_dimensions, "primary"
        )
        corrections.append("completed_goal_followup_preserved")
    elif understanding.user_act == "request_elaboration" and not (
        getattr(memory, "active_topic", None) or getattr(memory, "last_assistant_question", None)
    ):
        understanding.user_act = "new_request"
        understanding.topic_relation = "new_topic"
        corrections.append("orphan_elaboration_to_new_request")
    elif boundary.relation == "new_topic":
        understanding.user_act = "new_request"
        understanding.topic_relation = "new_topic"
        corrections.append("independent_goal_preserved_as_new_topic")
    elif boundary.relation == "same_topic_changed_scope":
        understanding.topic_relation = "same_topic"
        corrections.append("material_scope_change_detected")

    return understanding, corrections, boundary.to_dict()
