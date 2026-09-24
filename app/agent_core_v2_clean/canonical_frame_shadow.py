from __future__ import annotations
from copy import deepcopy
from typing import Any, Mapping
from .canonical_frame import build_frame,validate_frame

STORE_KEY="canonical_conversation_frame"
DIVERGENCE_KEY="canonical_divergences"


def _mapping(value: Any)->dict:
    return dict(value) if isinstance(value,Mapping) else {}


def _text(value: Any)->str:
    return " ".join(str(value or "").split())


def build_shadow_frame(store: dict, message: str, result: dict)->dict:
    previous=deepcopy(store.get(STORE_KEY) or {})
    frame=build_frame(message,result.get("understanding") or {},result.get("state_before") or {},store.get("answer_context") or {},previous)
    issues=validate_frame(frame)
    payload=frame.to_dict()
    payload["validation"]={"valid":not issues,"issues":issues}
    payload["mode"]="shadow"
    store[STORE_KEY]=deepcopy(payload)
    result[STORE_KEY]=deepcopy(payload)
    result[DIVERGENCE_KEY]=compare_runtime(result,payload)
    result.setdefault("functional_events",[])
    for issue in issues:
        result["functional_events"].append({"type":"canonical_frame_invariant","severity":"high","reason":issue,"shadow_only":True})
    return payload


def compare_runtime(result: Mapping[str,Any],frame: Mapping[str,Any])->list[dict]:
    out=[];u=_mapping(result.get("understanding"));topic=_mapping(frame.get("topic"));subject=_mapping(frame.get("subject"));operation=_mapping(frame.get("operation"))
    canonical_relation=_text(topic.get("relation"));runtime_relation=_text(u.get("topic_relation"))
    if canonical_relation in {"same_topic","same_topic_refinement"} and runtime_relation not in {"same_topic","same_topic_refinement"}:
        out.append({"type":"topic_relation_disagreement","severity":"high","runtime":runtime_relation or None,"canonical":canonical_relation})
    if _text(u.get("user_act")) in {"follow_up","answer_to_question","request_elaboration"} and not _text(subject.get("value")):
        out.append({"type":"subject_unresolved_for_followup","severity":"high","runtime_goal":_text(u.get("current_goal")) or None})
    state_after=_mapping(result.get("state_after"));runtime_topic=_text(state_after.get("active_topic"));op=_text(operation.get("text"));sub=_text(subject.get("value"))
    if sub and runtime_topic and op and runtime_topic.casefold()==op.casefold() and runtime_topic.casefold()!=sub.casefold():
        out.append({"type":"operation_promoted_to_runtime_topic","severity":"high","runtime_topic":runtime_topic,"canonical_subject":sub,"canonical_operation":op})
    retrieval=_mapping(result.get("retrieval"));query=_mapping(retrieval.get("query"));fields=_mapping(query.get("fields"));query_subject=_text(fields.get("subject"))
    if sub and query and not query_subject:
        out.append({"type":"retrieval_query_missing_canonical_subject","severity":"high","canonical_subject":sub,"query_text":_text(query.get("text"))})
    elif sub and query_subject and query_subject.casefold()!=sub.casefold():
        out.append({"type":"retrieval_subject_disagreement","severity":"high","runtime":query_subject,"canonical":sub})
    return out


def refresh_shadow_diagnostics(result: dict)->list[dict]:
    frame=_mapping(result.get(STORE_KEY))
    divergences=compare_runtime(result,frame) if frame else []
    result[DIVERGENCE_KEY]=divergences
    return divergences
