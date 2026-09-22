from __future__ import annotations
from copy import deepcopy
from typing import Any, Mapping

CASE_SIGNAL_TYPES={"symptom","observation","reported_failure","new_case","affected_scope","attempt_result"}
IN_SCOPE_INTENTS={"troubleshooting","procedural","requirements","conceptual","verification","compatibility"}
FAILURE_ACTS={"reported_failure","case_update","attempt_result","follow_up"}

def _mapping(value): return dict(value) if isinstance(value,Mapping) else {}
def _updates(value): return list(value) if isinstance(value,(list,tuple)) else []
def _is_resolved(state):
 pending=_mapping(state.get("pending_goal"));case=_mapping(state.get("support_case"));known=_mapping(pending.get("known_details"))
 return str(pending.get("status","")).casefold()=="complete" or str(known.get("resolution_status","")).casefold()=="resolved" or str(case.get("resolution_status","")).casefold()=="resolved"
def _has_case_signal(payload):
 return any(str(x.get("type","")).casefold() in CASE_SIGNAL_TYPES and str(x.get("value","")).strip() for x in _updates(payload.get("case_updates")) if isinstance(x,Mapping))
def _new_failure(payload):
 return (_has_case_signal(payload) or str(payload.get("user_act","")).casefold() in FAILURE_ACTS) and not bool(payload.get("goal_complete"))

def reconcile_understanding_object(understanding,memory,boundary=None):
 """Reconcile provider output before policy and memory mutation."""
 events=[];before=memory.to_dict() if hasattr(memory,"to_dict") else {}
 payload=understanding.to_dict() if hasattr(understanding,"to_dict") else _mapping(understanding)
 intent=str(payload.get("intent","")).casefold()
 if str(payload.get("domain_relevance","")).casefold()=="out_of_scope" and (intent in IN_SCOPE_INTENTS or _has_case_signal(payload)):
  understanding.domain_relevance="in_scope";events.append({"type":"scope_overridden","reason":"structured_domain_contradiction"})
 if _is_resolved(before) and _new_failure(payload):
  understanding.goal_complete=False
  updates=dict(getattr(understanding,"goal_updates",{}) or {});updates.pop("resolution_status",None);understanding.goal_updates=updates
  events.append({"type":"case_reopened","reason":"new_failure_after_resolution"})
 if boundary and boundary.get("relation")=="new_topic":
  understanding.topic_relation="new_topic"
  if getattr(understanding,"user_act",None) in {"follow_up","request_elaboration","answer_to_question"}: understanding.user_act="new_request"
  events.append({"type":"new_topic_scope_cleanup","reason":boundary.get("reason")})
 return understanding,events

def apply_reopen_transition(memory,events):
 if not any(x.get("type")=="case_reopened" for x in events): return
 memory.pending_goal.status="active";memory.pending_goal.missing_detail=None
 memory.pending_goal.known_details.pop("resolution_status",None)
 memory.support_case.status="reopened";memory.support_case.resolution_status="regressed"

def normalize_generation_flags(result):
 decision=_mapping(result.get("evidence_decision"));suff=_mapping(result.get("evidence_sufficiency"));retrieval=_mapping(result.get("retrieval"));semantic=_mapping(retrieval.get("semantic_fit"))
 if not semantic:return result
 accepted=bool(decision.get("accepted")) and bool(suff.get("generation_allowed"))
 semantic["accepted_for_generation"]=accepted;semantic["low_fit"]=not accepted
 retrieval["semantic_fit"]=semantic;result["retrieval"]=retrieval
 return result

def operation_target_fit(request,evidence):
 """Conservative structured check. Missing targets never manufacture a match."""
 rq=_mapping(request);ev=_mapping(evidence)
 rt=str(rq.get("target") or rq.get("object") or "").strip().casefold();et=str(ev.get("target") or ev.get("object") or "").strip().casefold()
 ro=str(rq.get("operation") or rq.get("verb") or "").strip().casefold();eo=str(ev.get("operation") or ev.get("verb") or "").strip().casefold()
 return {"accepted":bool(rt and et and rt==et and (not ro or not eo or ro==eo)),"target_match":bool(rt and et and rt==et),"operation_match":bool(not ro or not eo or ro==eo)}
