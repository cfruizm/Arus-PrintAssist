from __future__ import annotations
from dataclasses import dataclass, asdict
import re

_TOKEN_RE = re.compile(r"[\wáéíóúüñ]+", re.I)
STRUCTURAL = {"operation", "subject", "platform", "product", "component", "device", "scope"}
MATERIAL_SCOPE = {"platform", "product", "component", "device", "scope"}

@dataclass(frozen=True)
class TopicBoundary:
    relation: str
    reason: str
    shared_ratio: float
    changed_dimensions: list[str]
    introduced_dimensions: list[str]
    previous_evidence_role: str
    def to_dict(self): return asdict(self)

def _tokens(value):
    return {x.lower() for x in _TOKEN_RE.findall(str(value or "")) if len(x) > 2}

def infer_topic_boundary(previous_state: dict, understanding: dict) -> TopicBoundary:
    before = ((previous_state or {}).get("pending_goal") or {}).get("known_details") or {}
    now = (understanding or {}).get("goal_updates") or {}
    old_goal = ((previous_state or {}).get("pending_goal") or {}).get("summary") or ""
    new_goal = (understanding or {}).get("current_goal") or ""
    old = _tokens(old_goal) | _tokens(" ".join(str(before.get(k, "")) for k in STRUCTURAL))
    new = _tokens(new_goal) | _tokens(" ".join(str(now.get(k, "")) for k in STRUCTURAL))
    shared = len(old & new) / max(1, len(old | new))
    changed = sorted(k for k in STRUCTURAL if before.get(k) and now.get(k) and str(before[k]).strip().lower() != str(now[k]).strip().lower())
    introduced = sorted(k for k in MATERIAL_SCOPE if not before.get(k) and now.get(k))
    explicit = (understanding or {}).get("topic_relation") == "new_topic"
    independent = bool(new_goal and now.get("operation") and now.get("subject"))
    op_changed = "operation" in changed
    subject_changed = "subject" in changed
    if explicit or (independent and op_changed and subject_changed and shared < .50):
        return TopicBoundary("new_topic", "explicit_or_independent_goal_boundary", round(shared, 3), changed, introduced, "none")
    if any(k in MATERIAL_SCOPE for k in changed) or introduced:
        return TopicBoundary("same_topic_changed_scope", "material_scope_changed_or_introduced", round(shared, 3), changed, introduced, "comparison_only")
    return TopicBoundary("same_topic", "continuity_preserved", round(shared, 3), changed, introduced, "eligible")

def sanitize_new_topic_state(memory, understanding: dict, state_before: dict | None = None):
    updates = dict((understanding or {}).get("goal_updates") or {})
    prior = state_before or {}
    history = getattr(memory, "topic_history", None)
    prior_topic = prior.get("active_topic")
    prior_goal = prior.get("pending_goal") or {}
    if isinstance(history, list) and prior_topic:
        marker = (prior_topic, prior_goal.get("summary"), prior_goal.get("status"))
        exists = any((x.get("topic"), (x.get("goal") or {}).get("summary"), (x.get("goal") or {}).get("status")) == marker for x in history if isinstance(x, dict))
        if not exists:
            history.append({"topic": prior_topic, "goal": prior_goal})
    pending = getattr(memory, "pending_goal", None)
    if pending is not None:
        pending.known_details = updates
        pending.summary = (understanding or {}).get("current_goal", "")
        pending.intent = (understanding or {}).get("intent", "unknown")
    if hasattr(memory, "active_topic"):
        memory.active_topic = (understanding or {}).get("current_goal", "")
    records = getattr(memory, "fact_records", None)
    if isinstance(records, dict):
        keep = {k: v for k, v in records.items() if k not in STRUCTURAL}
        records.clear(); records.update(keep)
    case = getattr(memory, "support_case", None)
    if case is not None and (understanding or {}).get("intent") != "troubleshooting":
        case.status = "idle"; case.symptoms = []; case.observations = []; case.attempts = []; case.affected_scope = None; case.resolution_status = None
