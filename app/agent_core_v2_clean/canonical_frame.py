from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Mapping
import hashlib, json

VALID_RELATIONS={"new_topic","same_topic","same_topic_refinement","same_topic_changed_scope","return_to_previous","independent","same_topic_candidate"}
VALID_ORIGINS={"current_turn","conversation","canonical_history","user_confirmed","documented_context","authorized_evidence","none"}
TECHNICAL_INTENTS={"conceptual","procedural","troubleshooting","requirements","architecture","warranty","escalation"}


def _text(value: Any)->str:
    return " ".join(str(value or "").split())

def _mapping(value: Any)->dict:
    return dict(value) if isinstance(value,Mapping) else {}

def _first(*values: Any)->str:
    for value in values:
        value=_text(value)
        if value:return value
    return ""

def stable_topic_id(subject_type: str,subject_value: str)->str:
    if not subject_value:return ""
    payload=json.dumps({"type":_text(subject_type).casefold(),"value":_text(subject_value).casefold()},sort_keys=True,separators=(",",":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:20]

@dataclass
class CanonicalSubject:
    type:str="unknown";value:str="";canonical_id:str="";origin:str="none";confidence:float=0.0
@dataclass
class CanonicalOperation:
    intent:str="unknown";text:str="";current_message:str=""
@dataclass
class CanonicalTopic:
    topic_id:str="";relation:str="new_topic";status:str="active"
@dataclass
class CanonicalConversationFrame:
    schema_version:int=2;act:str="new_request";domain_relevance:str="uncertain"
    subject:CanonicalSubject=field(default_factory=CanonicalSubject)
    operation:CanonicalOperation=field(default_factory=CanonicalOperation)
    topic:CanonicalTopic=field(default_factory=CanonicalTopic)
    known_details:dict[str,str]=field(default_factory=dict)
    missing_material_details:list[str]=field(default_factory=list)
    retrieval_required:bool=False;case:dict[str,Any]=field(default_factory=dict)
    warnings:list[str]=field(default_factory=list);phase:str="pre_retrieval"
    def to_dict(self)->dict:return asdict(self)
    def query_fields(self)->dict:
        return {"subject_type":self.subject.type,"subject":self.subject.value,"subject_id":self.subject.canonical_id,"operation":self.operation.text,"intent":self.operation.intent,"current_message":self.operation.current_message,"topic_id":self.topic.topic_id,"topic_relation":self.topic.relation,"details":dict(self.known_details),"symptoms":list(self.case.get("symptoms") or []),"observations":list(self.case.get("observations") or []),"affected_scope":self.case.get("affected_scope")}

def _subject(kind,value,canonical_id="",origin="none",confidence=0.0):
    value=_text(value);return CanonicalSubject(kind if value else "unknown",value,_text(canonical_id),origin if value else "none",confidence if value else 0.0)

def subject_from_details(details)->CanonicalSubject:
    d=_mapping(details)
    for kind,key in (("product","product"),("product","platform"),("model","model"),("component","component"),("process","process"),("document","document"),("subject","subject")):
        if _text(d.get(key)):return _subject(kind,d[key],d.get("canonical_id"),"user_confirmed",1.0)
    return CanonicalSubject()

def subject_from_answer_context(context)->CanonicalSubject:
    c=_mapping(context);explicit=_mapping(c.get("canonical_subject"))
    if _text(explicit.get("value")):return _subject(_text(explicit.get("type")) or "subject",explicit["value"],explicit.get("canonical_id"),"documented_context",float(explicit.get("confidence") or .9))
    identities=[]
    for item in list(c.get("cited_evidence") or []):
        meta=_mapping(_mapping(item).get("metadata"));value=_first(meta.get("product"),meta.get("component"))
        if value:identities.append(value)
    unique={x.casefold():x for x in identities}
    if len(unique)==1:
        value=next(iter(unique.values()));return _subject("product",value,value,"documented_context",.7)
    return CanonicalSubject()

def _previous_subject(previous,registry)->CanonicalSubject:
    p=_mapping(previous);s=_mapping(p.get("subject"));value=_text(s.get("value"))
    if value:return _subject(_text(s.get("type")) or "subject",value,s.get("canonical_id"),"canonical_history",float(s.get("confidence") or .85))
    topic_id=_text(_mapping(p.get("topic")).get("topic_id"));record=_mapping(_mapping(registry).get(topic_id));s=_mapping(record.get("subject"));value=_text(s.get("value"))
    if value:return _subject(_text(s.get("type")) or "subject",value,s.get("canonical_id"),"canonical_history",float(s.get("confidence") or .85))
    return CanonicalSubject()

def _runtime_continuity(u)->bool:
    return _text(u.get("topic_relation")) in {"same_topic","same_topic_refinement"} or _text(u.get("user_act")) in {"follow_up","answer_to_question","request_elaboration"}

def build_frame(message,understanding,memory,answer_context=None,previous_frame=None,topic_registry=None)->CanonicalConversationFrame:
    u=_mapping(understanding);m=_mapping(memory);pending=_mapping(m.get("pending_goal"));details={**_mapping(pending.get("known_details")),**_mapping(u.get("goal_updates"))}
    explicit=subject_from_details(details);previous=_previous_subject(previous_frame,topic_registry);documented=subject_from_answer_context(answer_context)
    relation=_text(u.get("topic_relation")) or "new_topic";continuity=_runtime_continuity(u);warnings=[]
    if explicit.value:subject=explicit
    elif continuity and previous.value:subject=previous
    elif continuity and documented.value:subject=documented
    elif relation=="new_topic" and previous.value and not explicit.value:
        subject=previous;relation="same_topic_candidate";warnings.append("runtime_new_topic_without_new_subject")
    else:subject=CanonicalSubject()
    if continuity and not subject.value:warnings.append("follow_up_without_resolved_subject")
    if relation not in VALID_RELATIONS:warnings.append("noncanonical_topic_relation");relation="same_topic" if continuity else "new_topic"
    previous_topic=_text(_mapping(_mapping(previous_frame).get("topic")).get("topic_id"))
    topic_id=previous_topic if relation in {"same_topic","same_topic_refinement","same_topic_candidate"} and previous_topic else stable_topic_id(subject.type,subject.canonical_id or subject.value)
    operation=_first(u.get("current_goal"),message)
    runtime_intent=_text(u.get("intent"));pending_intent=_text(pending.get("intent"));prior_intent=_text(_mapping(_mapping(previous_frame).get("operation")).get("intent"))
    intent=runtime_intent if runtime_intent and runtime_intent!="unknown" else pending_intent if pending_intent and pending_intent!="unknown" else prior_intent if prior_intent and prior_intent!="unknown" else "unknown"
    case=_mapping(m.get("support_case"))
    if bool(u.get("should_retrieve")) and intent=="unknown":warnings.append("technical_intent_unresolved")
    if bool(u.get("should_retrieve")) and not subject.value:warnings.append("retrieval_without_subject")
    if intent=="troubleshooting" and not any((case.get("symptoms"),case.get("observations"),case.get("attempts"),case.get("affected_scope"))):warnings.append("troubleshooting_without_case_context")
    return CanonicalConversationFrame(act=_text(u.get("user_act")) or "new_request",domain_relevance=_text(u.get("domain_relevance")) or "uncertain",subject=subject,operation=CanonicalOperation(intent,operation,_text(message)),topic=CanonicalTopic(topic_id,relation,"active"),known_details={str(k):_text(v) for k,v in details.items() if _text(v)},missing_material_details=[_text(u.get("clarification_target"))] if u.get("needs_clarification") and _text(u.get("clarification_target")) else [],retrieval_required=bool(u.get("should_retrieve")),case={"symptoms":list(case.get("symptoms") or []),"observations":list(case.get("observations") or []),"attempts":list(case.get("attempts") or []),"affected_scope":case.get("affected_scope"),"resolution_status":case.get("resolution_status")},warnings=warnings)

def _authorized_subject(retrieval)->CanonicalSubject:
    r=_mapping(retrieval);verdict=_mapping(r.get("evidence_verdict"))
    if not verdict.get("accepted"):return CanonicalSubject()
    identities=[]
    for item in list(verdict.get("selected_evidence") or r.get("generation_evidence") or []):
        meta=_mapping(_mapping(item).get("metadata"));value=_first(meta.get("product"),meta.get("component"));kind="product" if _text(meta.get("product")) else "component"
        if value:identities.append((kind,value))
    unique={(k,v.casefold()):(k,v) for k,v in identities}
    if len(unique)==1:
        kind,value=next(iter(unique.values()));return _subject(kind,value,value,"authorized_evidence",.95)
    return CanonicalSubject()

def enrich_frame(frame_payload,retrieval,answer=None)->dict:
    payload=dict(frame_payload or {});subject=_mapping(payload.get("subject"));authorized=_authorized_subject(retrieval);warnings=list(payload.get("warnings") or [])
    if not _text(subject.get("value")) and authorized.value:
        payload["subject"]=asdict(authorized);subject=payload["subject"]
        topic=_mapping(payload.get("topic"));topic["topic_id"]=topic.get("topic_id") or stable_topic_id(authorized.type,authorized.canonical_id or authorized.value);payload["topic"]=topic
    elif not _text(subject.get("value")) and _mapping(retrieval).get("evidence_verdict",{}).get("accepted"):
        warnings.append("accepted_evidence_without_unambiguous_subject")
    if _mapping(answer).get("mode") in {"documented_answer","documented_answer_partial"} and not _text(_mapping(payload.get("topic")).get("topic_id")):warnings.append("documented_answer_without_topic_identity")
    payload["warnings"]=sorted(set(warnings));payload["phase"]="post_retrieval";return payload

def validate_frame_payload(payload)->list[str]:
    p=_mapping(payload);issues=[];topic=_mapping(p.get("topic"));subject=_mapping(p.get("subject"));operation=_mapping(p.get("operation"))
    if _text(topic.get("relation")) in {"same_topic","same_topic_refinement","same_topic_candidate"} and not _text(topic.get("topic_id")):issues.append("same_topic_requires_topic_id")
    if p.get("retrieval_required") and not _text(operation.get("text")):issues.append("retrieval_requires_operation")
    if _text(subject.get("origin")) not in VALID_ORIGINS:issues.append("invalid_subject_origin")
    return issues

def validate_frame(frame)->list[str]:return validate_frame_payload(frame.to_dict())
