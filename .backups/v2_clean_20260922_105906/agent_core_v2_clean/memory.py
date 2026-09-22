from __future__ import annotations
from copy import deepcopy
import hashlib, re, unicodedata
from .models import ConversationMemory, TurnUnderstanding

STRUCTURAL_GOAL_KEYS={"intent","status","summary","current_goal","goal_complete","missing_detail","topic"}
ALLOWED_CASE_UPDATE_TYPES={"symptom","observation","affected_scope","attempted_action","attempt_result","error_message","evidence","resolution_status"}

def _norm(v):
    return " ".join(str(v or "").split()).strip()

def normalize_text(v):
    return unicodedata.normalize("NFKD", _norm(v)).encode("ascii","ignore").decode().casefold()

def normalize_goal_updates(values):
    clean={};removed=[]
    for k,v in dict(values or {}).items():
        key=str(k).strip()
        if key in STRUCTURAL_GOAL_KEYS: removed.append(key); continue
        value=_norm(v)
        if key and value: clean[key]=value
    return clean,removed

def _record_fact(memory,key,value,turn):
    value=_norm(value)
    if not value:return
    ident=f"fact:{hashlib.sha1(normalize_text(key+':'+value).encode()).hexdigest()[:12]}"
    memory.fact_records[ident]={"key":key,"value":value,"turn":turn,"status":"confirmed"}

def _append_unique(values,value):
    value=_norm(value)
    if value and normalize_text(value) not in {normalize_text(x) for x in values}: values.append(value)

def apply_understanding(memory: ConversationMemory, u: TurnUnderstanding):
    previous_topic=memory.active_topic
    rel=str(u.topic_relation or "same_topic")
    if rel in {"new_topic","independent"}:
        if memory.active_topic or memory.pending_goal.summary:
            memory.topic_history.append({"topic":memory.active_topic,"goal":memory.pending_goal.summary,"turn":memory.turn_number})
            memory.case_history.append({"topic":memory.active_topic,"goal":memory.pending_goal.summary,"goal_state":deepcopy(memory.pending_goal.__dict__),"case_state":deepcopy(memory.support_case.__dict__),"turn":memory.turn_number})
        memory.active_topic=u.current_goal or None
        memory.pending_goal=type(memory.pending_goal)()
        memory.support_case=type(memory.support_case)()
    elif rel=="return_to_previous" and memory.topic_history:
        target=str(memory.topic_history[-1].get("topic") or memory.active_topic or "") or None
        memory.active_topic=target
        for item in reversed(memory.case_history):
            if str(item.get("topic") or "") == target:
                from .models import PendingGoal, SupportCase
                memory.pending_goal=PendingGoal(**dict(item.get("goal_state") or {}))
                memory.support_case=SupportCase(**dict(item.get("case_state") or {}))
                break

    goal=u.current_goal or memory.pending_goal.summary
    if goal:
        memory.pending_goal.summary=goal
        memory.pending_goal.intent=u.intent
        if u.goal_complete:
            memory.pending_goal.status="complete"
        else:
            memory.pending_goal.status="active"
    for key,value in (u.goal_updates or {}).items():
        clean_key=str(key).strip();value=_norm(value)
        if not clean_key or not value or clean_key in STRUCTURAL_GOAL_KEYS:continue
        memory.pending_goal.known_details[clean_key]=value
        _record_fact(memory,clean_key,value,memory.turn_number)

    for item in u.case_updates or []:
        typ=str(item.get("type") or "").strip();value=_norm(item.get("value"))
        if typ not in ALLOWED_CASE_UPDATE_TYPES or not value:continue
        if typ=="symptom":_append_unique(memory.support_case.symptoms,value)
        elif typ=="observation":_append_unique(memory.support_case.observations,value)
        elif typ=="affected_scope":memory.support_case.affected_scope=value
        elif typ=="attempted_action":
            if not any(normalize_text(x.get("action"))==normalize_text(value) for x in memory.support_case.attempts):
                memory.support_case.attempts.append({"action":value,"result":None})
        elif typ=="attempt_result":
            if memory.support_case.attempts:
                memory.support_case.attempts[-1]["result"]=value
            else:
                memory.support_case.attempts.append({"action":None,"result":value})
            memory.support_case.resolution_status="unresolved" if normalize_text(value) in {"failed","no resolvio","same"} else memory.support_case.resolution_status
        elif typ=="error_message":_append_unique(memory.support_case.observations,f"Mensaje: {value}")
        elif typ=="evidence":_append_unique(memory.support_case.observations,f"Evidencia: {value}")
        elif typ=="resolution_status":memory.support_case.resolution_status=value

    if u.intent=="troubleshooting" or u.case_updates:
        memory.support_case.status="resolved" if u.goal_complete and memory.support_case.resolution_status=="resolved" else "diagnosing"
    memory.turn_number += 1

def compact_context(memory: ConversationMemory):
    return {
        "active_topic":memory.active_topic,
        "pending_goal":{"summary":memory.pending_goal.summary,"intent":memory.pending_goal.intent,"known_details":dict(memory.pending_goal.known_details),"missing_detail":memory.pending_goal.missing_detail,"status":memory.pending_goal.status},
        "support_case":{"status":memory.support_case.status,"symptoms":list(memory.support_case.symptoms),"observations":list(memory.support_case.observations[-4:]),"attempts":deepcopy(memory.support_case.attempts[-6:]),"affected_scope":memory.support_case.affected_scope,"resolution_status":memory.support_case.resolution_status},
        "last_assistant_question":memory.last_assistant_question,
        "topic_history":list(memory.topic_history[-4:]),
    }

def failed_actions(memory):
    return [str(x.get("action") or "") for x in memory.support_case.attempts if str(x.get("result") or "").strip().casefold() in {"failed","no resolvio","same","no funciono","sin cambios"}]
