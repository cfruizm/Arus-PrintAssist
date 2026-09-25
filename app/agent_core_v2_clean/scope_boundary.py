from __future__ import annotations
from dataclasses import dataclass, asdict

_EXTERNAL_RELATIONS = {"new_topic", "independent"}
_EXTERNAL_ACTS = {"new_request", "independent_question", "topic_change"}
_NON_DOMAIN_INTENTS = {"social", "cancel", "escalation", "meta", "capabilities"}

@dataclass(frozen=True)
class ScopeBoundaryDecision:
    original_relevance: str
    final_relevance: str
    blocked_before_retrieval: bool
    preserve_technical_state: bool
    reason: str
    def to_dict(self):
        return asdict(self)

def reconcile_scope_boundary(understanding, memory):
    """Resolve domain scope before entity, topic, memory, retrieval, or answer planning.

    The policy is structural and domain-independent: an uncertain standalone request is
    not allowed to consume the technical RAG or internal-knowledge route. Continuations
    of an active support goal remain eligible for the normal technical reconciliation.
    """
    original = str(getattr(understanding, "domain_relevance", "") or "uncertain").casefold()
    relation = str(getattr(understanding, "topic_relation", "") or "").casefold()
    act = str(getattr(understanding, "user_act", "") or "").casefold()
    intent = str(getattr(understanding, "intent", "") or "").casefold()
    has_active = bool(getattr(memory, "active_topic", None) or getattr(getattr(memory, "pending_goal", None), "summary", None))
    continuation = relation in {"same_topic", "return_to_previous"} or act in {"follow_up", "answer_to_question", "request_elaboration", "attempt_result", "reported_failure"}
    standalone_uncertain = original == "uncertain" and relation in _EXTERNAL_RELATIONS and act in _EXTERNAL_ACTS and intent not in _NON_DOMAIN_INTENTS
    explicit_external = original == "out_of_scope"
    blocked = explicit_external or (standalone_uncertain and not continuation)
    if blocked:
        understanding.domain_relevance = "out_of_scope"
        understanding.should_retrieve = False
        understanding.needs_clarification = False
        understanding.clarification_target = None
        reason = "provider_out_of_scope" if explicit_external else "uncertain_independent_request_closed_at_domain_boundary"
    else:
        reason = "active_support_continuation_preserved" if original == "uncertain" and has_active and continuation else "provider_scope_preserved"
    return understanding, ScopeBoundaryDecision(original, str(understanding.domain_relevance), blocked, blocked, reason)
