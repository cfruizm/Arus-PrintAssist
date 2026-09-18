from __future__ import annotations
from dataclasses import asdict, dataclass
import re
import unicodedata

_TOKEN_RE = re.compile(r"[\wáéíóúüñ]+", re.I)
STRUCTURAL = {"operation", "subject", "platform", "product", "component", "device", "scope"}
MATERIAL_SCOPE = {"platform", "product", "component", "device", "scope"}
_REFERENTIAL_ACTS = {"request_elaboration", "answer", "confirmation", "correction", "continue"}
_REFINEMENT_MARKERS = {"paso", "parte", "opcion", "campo", "despues", "antes", "siguiente", "donde", "cual", "cuando", "como", "porque", "eso", "esa", "ese", "esto", "esta", "that", "this", "it", "step", "option", "field", "next", "after", "before", "where", "which"}

@dataclass(frozen=True)
class TopicBoundary:
    relation: str
    reason: str
    shared_ratio: float
    changed_dimensions: list[str]
    introduced_dimensions: list[str]
    previous_evidence_role: str
    def to_dict(self): return asdict(self)

def _norm(value):
    return unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold()

def _tokens(value):
    return {x.casefold() for x in _TOKEN_RE.findall(_norm(value)) if len(x) > 2}

def _is_refinement(previous_state, understanding, old, new, changed, introduced):
    pending = (previous_state or {}).get("pending_goal") or {}
    if not pending.get("summary") or introduced: return False
    relation = str((understanding or {}).get("topic_relation") or "")
    act = str((understanding or {}).get("user_act") or "")
    if relation == "same_topic" or act in _REFERENTIAL_ACTS: return True
    markers = new & _REFINEMENT_MARKERS
    subject_only_change = set(changed).issubset({"operation", "subject"})
    lexical_containment = bool(old & new) and len(old & new) / max(1, len(new)) >= 0.20
    return subject_only_change and bool(markers) and lexical_containment

def infer_topic_boundary(previous_state: dict, understanding: dict) -> TopicBoundary:
    before = ((previous_state or {}).get("pending_goal") or {}).get("known_details") or {}
    now = (understanding or {}).get("goal_updates") or {}
    old_goal = ((previous_state or {}).get("pending_goal") or {}).get("summary") or ""
    new_goal = (understanding or {}).get("current_goal") or ""
    old = _tokens(old_goal) | _tokens(" ".join(str(before.get(k, "")) for k in STRUCTURAL))
    new = _tokens(new_goal) | _tokens(" ".join(str(now.get(k, "")) for k in STRUCTURAL))
    shared = len(old & new) / max(1, len(old | new))
    changed = sorted(k for k in STRUCTURAL if before.get(k) and now.get(k) and _norm(before[k]) != _norm(now[k]))
    introduced = sorted(k for k in MATERIAL_SCOPE if not before.get(k) and now.get(k))
    if _is_refinement(previous_state, understanding, old, new, changed, introduced):
        return TopicBoundary("same_topic_refinement", "referential_or_contained_goal_refinement", round(shared, 3), changed, introduced, "primary")
    explicit_new = (understanding or {}).get("topic_relation") == "new_topic"
    lexical_goal_change = bool(old and new and shared < .18 and len(new-old) >= 2)
    independent = bool(new_goal and now.get("operation") and now.get("subject"))
    if explicit_new or lexical_goal_change or (independent and {"operation", "subject"}.issubset(changed) and shared < .50):
        return TopicBoundary("new_topic", "explicit_or_independent_goal_boundary", round(shared, 3), changed, introduced, "none")
    if any(k in MATERIAL_SCOPE for k in changed) or introduced:
        return TopicBoundary("same_topic_changed_scope", "material_scope_changed", round(shared, 3), changed, introduced, "comparison_only")
    return TopicBoundary("same_topic", "continuity_preserved", round(shared, 3), changed, introduced, "eligible")

def sanitize_new_topic_state(memory, understanding: dict, previous_state: dict | None = None):
    pending = getattr(memory, "pending_goal", None)
    if pending is not None:
        pending.known_details = dict((understanding or {}).get("goal_updates") or {})
        pending.summary = str((understanding or {}).get("current_goal") or "")
    if hasattr(memory, "fact_records"): memory.fact_records = {}
