from __future__ import annotations
from copy import deepcopy
from typing import Any,Mapping
from .canonical_frame import build_frame,enrich_frame,validate_frame_payload
STORE_KEY="canonical_conversation_frame";REGISTRY_KEY="canonical_topic_registry";DIVERGENCE_KEY="canonical_divergences"
def _mapping(v):return dict(v) if isinstance(v,Mapping) else {}
def _text(v):return " ".join(str(v or "").split())
def _finalize(payload):
    issues=validate_frame_payload(payload);payload["validation"]={"valid":not issues,"issues":issues};payload["mode"]="shadow";return payload
def build_shadow_frame(store,message,result):
    previous=deepcopy(store.get(STORE_KEY) or {});registry=store.setdefault(REGISTRY_KEY,{})
    frame=build_frame(message,result.get("understanding") or {},result.get("state_before") or {},store.get("answer_context") or {},previous,registry)
    payload=_finalize(frame.to_dict());store[STORE_KEY]=deepcopy(payload);result[STORE_KEY]=deepcopy(payload)
    result[DIVERGENCE_KEY]=compare_runtime(result,payload);_events(result,payload);return payload
def enrich_shadow_frame(store,result):
    payload=enrich_frame(result.get(STORE_KEY) or store.get(STORE_KEY) or {},result.get("retrieval") or {},result.get("answer") or {})
    payload=_finalize(payload);store[STORE_KEY]=deepcopy(payload);result[STORE_KEY]=deepcopy(payload)
    result[DIVERGENCE_KEY]=compare_runtime(result,payload);_commit(store,payload,result);_events(result,payload);return payload
def _commit(store,payload,result):
    topic=_mapping(payload.get("topic"));topic_id=_text(topic.get("topic_id"));subject=_mapping(payload.get("subject"))
    if not topic_id or not _text(subject.get("value")):return
    registry=store.setdefault(REGISTRY_KEY,{});record=registry.setdefault(topic_id,{})
    record.update({"subject":deepcopy(subject),"last_operation":deepcopy(payload.get("operation") or {}),"case":deepcopy(payload.get("case") or {}),"last_answer_mode":_text(_mapping(result.get("answer")).get("mode"))})
    context=result.get("answer_context") or {}
    if _mapping(result.get("answer")).get("mode") in {"documented_answer","documented_answer_partial"}:record["documented_context"]=deepcopy(context)
def compare_runtime(result,frame):
    out=[];u=_mapping(result.get("understanding"));subject=_mapping(frame.get("subject"));topic=_mapping(frame.get("topic"));operation=_mapping(frame.get("operation"));sub=_text(subject.get("value"));relation=_text(topic.get("relation"));runtime_relation=_text(u.get("topic_relation"))
    if relation in {"same_topic","same_topic_refinement","same_topic_candidate"} and runtime_relation not in {"same_topic","same_topic_refinement"}:out.append({"type":"topic_relation_disagreement","severity":"high","runtime":runtime_relation or None,"canonical":relation})
    if "runtime_new_topic_without_new_subject" in (frame.get("warnings") or []):out.append({"type":"canonical_history_discarded","severity":"high","canonical_subject":sub or None})
    if frame.get("retrieval_required") and not sub:out.append({"type":"retrieval_without_subject","severity":"high"})
    if "technical_intent_unresolved" in (frame.get("warnings") or []):out.append({"type":"technical_intent_unknown","severity":"high"})
    if "troubleshooting_without_case_context" in (frame.get("warnings") or []):out.append({"type":"troubleshooting_without_case_context","severity":"high"})
    retrieval=_mapping(result.get("retrieval"));query=_mapping(retrieval.get("query"));fields=_mapping(query.get("fields"));query_subject=_text(fields.get("subject"))
    if sub and query and not query_subject:out.append({"type":"retrieval_query_missing_canonical_subject","severity":"high","canonical_subject":sub,"query_text":_text(query.get("text"))})
    state_after=_mapping(result.get("state_after"));runtime_topic=_text(state_after.get("active_topic"));op=_text(operation.get("text"))
    if sub and runtime_topic and op and runtime_topic.casefold()==op.casefold() and runtime_topic.casefold()!=sub.casefold():out.append({"type":"operation_promoted_to_runtime_topic","severity":"high","runtime_topic":runtime_topic,"canonical_subject":sub,"canonical_operation":op})
    return out
def refresh_shadow_diagnostics(result):
    result[DIVERGENCE_KEY]=compare_runtime(result,_mapping(result.get(STORE_KEY)));return result[DIVERGENCE_KEY]
def _events(result,payload):
    events=result.setdefault("functional_events",[]);existing={(e.get("type"),e.get("reason")) for e in events}
    for issue in _mapping(payload.get("validation")).get("issues") or []:
        key=("canonical_frame_invariant",issue)
        if key not in existing:events.append({"type":key[0],"severity":"high","reason":issue,"shadow_only":True})
