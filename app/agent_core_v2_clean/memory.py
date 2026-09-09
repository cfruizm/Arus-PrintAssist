from .models import ConversationMemory,TurnUnderstanding,PendingGoal

STRUCTURAL_GOAL_KEYS={"intent","status","summary","known_details","missing_detail","goal_complete","current_goal"}

def normalize_goal_updates(updates):
 raw=dict(updates or {})
 clean={str(k):str(v) for k,v in raw.items() if str(k) not in STRUCTURAL_GOAL_KEYS and str(v).strip()}
 return clean,sorted(set(map(str,raw))-set(clean))

def _add(xs,v):
 v=" ".join(str(v or "").split())
 if v and v.casefold() not in {x.casefold() for x in xs}:xs.append(v)

def apply_understanding(m,u):
 if u.degraded:
  m.turn_number+=1
  return
 if u.topic_relation in {"new_topic","independent"} and u.domain_relevance=="in_scope" and m.active_topic and u.current_goal!=m.active_topic:
  m.topic_history.append({"topic":m.active_topic,"goal":m.pending_goal.summary,"case":m.support_case.__dict__.copy()})
  m.pending_goal=PendingGoal();m.support_case=type(m.support_case)()
 if u.domain_relevance=="in_scope":
  m.active_topic=u.current_goal or m.active_topic
  if u.current_goal:
   m.pending_goal.summary=u.current_goal
   if u.intent!="unknown":m.pending_goal.intent=u.intent
   m.pending_goal.status="complete" if u.goal_complete else "active"
   m.pending_goal.missing_detail=u.clarification_target if u.needs_clarification else None
  clean,_=normalize_goal_updates(u.goal_updates)
  m.pending_goal.known_details.update(clean)
  for f in u.case_updates:
   k,v=str(f.get("type") or ""),str(f.get("value") or "").strip()
   if k in {"symptom","reported_failure","new_case"}:_add(m.support_case.symptoms,v);m.support_case.status="diagnosing"
   elif k=="observation":_add(m.support_case.observations,v);m.support_case.status="diagnosing"
   elif k=="affected_scope":m.support_case.affected_scope=v;m.support_case.status="diagnosing"
   elif k=="attempted_action":m.support_case.attempts.append({"action":v,"result":None});m.support_case.status="diagnosing"
   elif k=="attempt_result":
    if m.support_case.attempts:m.support_case.attempts[-1]["result"]=v
    else:m.support_case.attempts.append({"action":"previous validation","result":v})
    m.support_case.status="diagnosing"
 m.turn_number+=1

def compact_context(m):
 return {"active_topic":m.active_topic,"pending_goal":m.pending_goal.__dict__,"support_case":m.support_case.__dict__,"last_assistant_question":m.last_assistant_question,"summary":m.summary,"recent_topics":m.topic_history[-2:]}
