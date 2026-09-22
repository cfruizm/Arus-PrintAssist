from __future__ import annotations
from typing import Mapping
CASE_SIGNAL_TYPES={"symptom","observation","reported_failure","new_case","affected_scope","attempt_result"}
IN_SCOPE_INTENTS={"troubleshooting","procedural","requirements","conceptual","verification","compatibility"}
def _map(v):return dict(v) if isinstance(v,Mapping) else {}
def _items(v):return list(v) if isinstance(v,(list,tuple)) else []
def _has_signal(p):return any(str(x.get("type","")).casefold() in CASE_SIGNAL_TYPES and str(x.get("value","")).strip() for x in _items(p.get("case_updates")) if isinstance(x,Mapping))
def _resolved(state):
 c=_map(state.get("support_case"));k=_map(_map(state.get("pending_goal")).get("known_details"))
 return str(c.get("resolution_status","")).casefold()=="resolved" or str(k.get("resolution_status","")).casefold()=="resolved"
def reconcile_understanding_object(u,memory,boundary=None):
 events=[];p=u.to_dict();before=memory.to_dict();intent=str(p.get("intent","")).casefold()
 if str(p.get("domain_relevance","")).casefold()=="out_of_scope" and (intent in IN_SCOPE_INTENTS or _has_signal(p)):
  u.domain_relevance="in_scope";events.append({"type":"scope_overridden","reason":"structured_domain_contradiction"})
 if _resolved(before) and (_has_signal(p) or str(p.get("user_act","")).casefold() in {"reported_failure","case_update","attempt_result"}) and not p.get("goal_complete"):
  u.goal_complete=False;updates=dict(u.goal_updates or {});updates.pop("resolution_status",None);u.goal_updates=updates;events.append({"type":"case_reopened","reason":"new_failure_after_resolution"})
 return u,events
def apply_reopen_transition(memory,events):
 if any(x.get("type")=="case_reopened" for x in events):
  memory.pending_goal.status="active";memory.pending_goal.missing_detail=None;memory.pending_goal.known_details.pop("resolution_status",None);memory.support_case.status="reopened";memory.support_case.resolution_status="regressed"
def normalize_generation_flags(result):
 d=_map(result.get("evidence_decision"));s=_map(result.get("evidence_sufficiency"));r=_map(result.get("retrieval"));f=_map(r.get("semantic_fit"))
 if f:
  accepted=bool(d.get("accepted")) and bool(s.get("generation_allowed"));f["accepted_for_generation"]=accepted;f["low_fit"]=not accepted;r["semantic_fit"]=f;result["retrieval"]=r
 return result
