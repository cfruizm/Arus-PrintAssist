from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Mapping
import hashlib, json

VALID_RELATIONS={"new_topic","same_topic","same_topic_refinement","same_topic_changed_scope","return_to_previous","independent"}
VALID_ORIGINS={"current_turn","conversation","user_confirmed","documented_context","none"}


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def _first(*values: Any) -> str:
    for value in values:
        value=_text(value)
        if value:return value
    return ""


def stable_topic_id(subject_type: str, subject_value: str) -> str:
    payload=json.dumps({"type":_text(subject_type).casefold(),"value":_text(subject_value).casefold()},sort_keys=True,separators=(",",":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20] if subject_value else ""

@dataclass
class CanonicalSubject:
    type: str="unknown"
    value: str=""
    canonical_id: str=""
    origin: str="none"
    confidence: float=0.0

@dataclass
class CanonicalOperation:
    intent: str="unknown"
    text: str=""
    current_message: str=""

@dataclass
class CanonicalTopic:
    topic_id: str=""
    relation: str="new_topic"
    status: str="active"

@dataclass
class CanonicalConversationFrame:
    schema_version: int=1
    act: str="new_request"
    domain_relevance: str="uncertain"
    subject: CanonicalSubject=field(default_factory=CanonicalSubject)
    operation: CanonicalOperation=field(default_factory=CanonicalOperation)
    topic: CanonicalTopic=field(default_factory=CanonicalTopic)
    known_details: dict[str,str]=field(default_factory=dict)
    missing_material_details: list[str]=field(default_factory=list)
    retrieval_required: bool=False
    case: dict[str,Any]=field(default_factory=dict)
    warnings: list[str]=field(default_factory=list)

    def to_dict(self)->dict:
        return asdict(self)

    def query_fields(self)->dict:
        return {
            "subject_type":self.subject.type,
            "subject":self.subject.value,
            "subject_id":self.subject.canonical_id,
            "operation":self.operation.text,
            "intent":self.operation.intent,
            "current_message":self.operation.current_message,
            "topic_id":self.topic.topic_id,
            "topic_relation":self.topic.relation,
            "details":dict(self.known_details),
            "symptoms":list(self.case.get("symptoms") or []),
            "observations":list(self.case.get("observations") or []),
            "affected_scope":self.case.get("affected_scope"),
        }


def subject_from_details(details: Mapping[str,Any] | None)->CanonicalSubject:
    details=_mapping(details)
    candidates=(
        ("product",details.get("product")),("product",details.get("platform")),
        ("model",details.get("model")),("component",details.get("component")),
        ("process",details.get("process")),("document",details.get("document")),
        ("subject",details.get("subject")),
    )
    for kind,value in candidates:
        value=_text(value)
        if value:return CanonicalSubject(kind,value,_text(details.get("canonical_id")),"user_confirmed",1.0)
    return CanonicalSubject()


def subject_from_answer_context(context: Mapping[str,Any] | None)->CanonicalSubject:
    context=_mapping(context)
    explicit=_mapping(context.get("canonical_subject"))
    value=_text(explicit.get("value"))
    if value:
        return CanonicalSubject(_text(explicit.get("type")) or "subject",value,_text(explicit.get("canonical_id")),"documented_context",float(explicit.get("confidence") or .9))
    evidence=list(context.get("cited_evidence") or [])
    identities=[]
    for item in evidence:
        meta=_mapping(_mapping(item).get("metadata"))
        value=_first(meta.get("product"),meta.get("component"))
        if value:identities.append(value)
    if identities and len({x.casefold() for x in identities})==1:
        value=identities[0]
        return CanonicalSubject("product",value,value,"documented_context",.7)
    return CanonicalSubject()


def build_frame(message: str, understanding: Mapping[str,Any], memory: Mapping[str,Any], answer_context: Mapping[str,Any] | None=None, previous_frame: Mapping[str,Any] | None=None)->CanonicalConversationFrame:
    u=_mapping(understanding);m=_mapping(memory);pending=_mapping(m.get("pending_goal"));details={**_mapping(pending.get("known_details")),**_mapping(u.get("goal_updates"))}
    previous=_mapping(previous_frame);previous_subject=_mapping(previous.get("subject"))
    explicit=subject_from_details(details)
    relation=_text(u.get("topic_relation")) or "new_topic"
    follow=relation in {"same_topic","same_topic_refinement"} or _text(u.get("user_act")) in {"follow_up","answer_to_question","request_elaboration"}
    if explicit.value:
        subject=explicit
    elif follow and _text(previous_subject.get("value")):
        subject=CanonicalSubject(_text(previous_subject.get("type")) or "subject",_text(previous_subject.get("value")),_text(previous_subject.get("canonical_id")),"conversation",float(previous_subject.get("confidence") or .9))
    elif follow:
        subject=subject_from_answer_context(answer_context)
    else:
        subject=CanonicalSubject()
    warnings=[]
    if follow and not subject.value:warnings.append("follow_up_without_resolved_subject")
    if relation not in VALID_RELATIONS:
        warnings.append("noncanonical_topic_relation");relation="same_topic" if follow else "new_topic"
    topic_id=stable_topic_id(subject.type,subject.canonical_id or subject.value)
    old_topic=_text(_mapping(previous.get("topic")).get("topic_id"))
    if follow and old_topic:topic_id=old_topic
    operation_text=_first(u.get("current_goal"),message)
    case=_mapping(m.get("support_case"))
    frame=CanonicalConversationFrame(
        act=_text(u.get("user_act")) or "new_request",
        domain_relevance=_text(u.get("domain_relevance")) or "uncertain",
        subject=subject,
        operation=CanonicalOperation(_text(u.get("intent")) or _text(pending.get("intent")) or "unknown",operation_text,_text(message)),
        topic=CanonicalTopic(topic_id,relation,"active"),
        known_details={str(k):_text(v) for k,v in details.items() if _text(v)},
        missing_material_details=[_text(u.get("clarification_target"))] if u.get("needs_clarification") and _text(u.get("clarification_target")) else [],
        retrieval_required=bool(u.get("should_retrieve")),
        case={"symptoms":list(case.get("symptoms") or []),"observations":list(case.get("observations") or []),"attempts":list(case.get("attempts") or []),"affected_scope":case.get("affected_scope"),"resolution_status":case.get("resolution_status")},
        warnings=warnings,
    )
    return frame


def validate_frame(frame: CanonicalConversationFrame)->list[str]:
    issues=[]
    if frame.act in {"follow_up","answer_to_question","request_elaboration"} and not frame.subject.value:issues.append("follow_up_requires_subject")
    if frame.topic.relation in {"same_topic","same_topic_refinement"} and not frame.topic.topic_id:issues.append("same_topic_requires_topic_id")
    if frame.retrieval_required and not frame.operation.text:issues.append("retrieval_requires_operation")
    if frame.subject.origin not in VALID_ORIGINS:issues.append("invalid_subject_origin")
    return issues
