from __future__ import annotations
from dataclasses import dataclass, asdict

_EXTERNAL_RELATIONS={"new_topic","independent"}
_EXTERNAL_ACTS={"new_request","independent_question","topic_change"}
_NON_DOMAIN_INTENTS={"social","cancel","escalation","meta","capabilities"}
@dataclass(frozen=True)
class ScopeBoundaryDecision:
 original_relevance:str;final_relevance:str;blocked_before_retrieval:bool;preserve_technical_state:bool;reason:str
 def to_dict(self):return asdict(self)
def reconcile_scope_boundary(u,memory):
 original=str(getattr(u,"domain_relevance","") or "uncertain").casefold();relation=str(getattr(u,"topic_relation","") or "").casefold();act=str(getattr(u,"user_act","") or "").casefold();intent=str(getattr(u,"intent","") or "").casefold()
 continuation=relation in {"same_topic","return_to_previous"} or act in {"follow_up","answer_to_question","request_elaboration","attempt_result","reported_failure"}
 standalone=original=="uncertain" and relation in _EXTERNAL_RELATIONS and act in _EXTERNAL_ACTS and intent not in _NON_DOMAIN_INTENTS
 blocked=original=="out_of_scope" or (standalone and not continuation)
 if blocked:
  u.domain_relevance="out_of_scope";u.should_retrieve=False;u.needs_clarification=False;u.clarification_target=None;reason="provider_out_of_scope" if original=="out_of_scope" else "uncertain_independent_request_closed_at_domain_boundary"
 else:reason="provider_scope_preserved"
 return u,ScopeBoundaryDecision(original,str(u.domain_relevance),blocked,blocked,reason)
