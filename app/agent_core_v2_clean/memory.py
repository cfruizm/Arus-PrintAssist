from .models import ConversationMemory,TurnUnderstanding,PendingGoal
STRUCTURAL_GOAL_KEYS={"intent","status","summary","known_details","missing_detail","goal_complete","current_goal","goal_type","goal_updates","answer_to_question"}
def normalize_goal_updates(updates):
 raw=dict(updates or {});clean={str(k):str(v) for k,v in raw.items() if str(k) not in STRUCTURAL_GOAL_KEYS and str(v).strip()};return clean,sorted(set(map(str,raw))-set(clean))
def _add(xs,v):
 v=" ".join(str(v or "").split())
 if v and v.casefold() not in {x.casefold() for x in xs}:xs.append(v)
def _record_user_facts(m,clean):
 for k,v in clean.items():m.fact_records[str(k)]={"key":str(k),"value":str(v),"origin":"user","status":"confirmed","turn":m.turn_number+1}
def apply_understanding(m,u):
 if u.degraded:m.turn_number+=1;return
 answering=u.user_act=="answer_to_question" and bool(m.last_assistant_question)
 if not answering and u.topic_relation in {"new_topic","independent"} and u.domain_relevance=="in_scope" and m.active_topic and u.current_goal!=m.active_topic:
  m.topic_history.append({"topic":m.active_topic,"goal":m.pending_goal.summary,"case":m.support_case.__dict__.copy()});m.pending_goal=PendingGoal();m.support_case=type(m.support_case)();m.fact_records={}
 if u.domain_relevance=="in_scope":
  if not answering:
   m.active_topic=u.current_goal or m.active_topic
   if u.current_goal:m.pending_goal.summary=u.current_goal
  if u.intent!="unknown" and not answering:m.pending_goal.intent=u.intent
  clean,_=normalize_goal_updates(u.goal_updates);m.pending_goal.known_details.update(clean);_record_user_facts(m,clean)
  if u.needs_clarification and u.clarification_target:m.pending_goal.missing_detail=u.clarification_target;m.pending_goal.status="waiting_user"
  else:m.pending_goal.missing_detail=None;m.pending_goal.status="complete" if u.goal_complete else "active"
  case_updates=list(u.case_updates or [])
  if u.intent=="troubleshooting" and answering and m.last_assistant_question and not case_updates:
   raw=str((u.goal_updates or {}).get("answer_to_question") or "").strip()
   if raw:case_updates.append({"type":"observation","value":"Pregunta: "+m.last_assistant_question+" Respuesta: "+raw})
  if u.intent=="troubleshooting":
   present={str(x.get("type") or "") for x in case_updates}
   for key in ("symptom","observation","affected_scope","attempted_action","attempt_result"):
    value=str(clean.get(key) or "").strip()
    if value and key not in present:case_updates.append({"type":key,"value":value})
  for f in case_updates:
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
def compact_context(m):return {"active_topic":m.active_topic,"pending_goal":m.pending_goal.__dict__,"confirmed_facts":list(m.fact_records.values()),"support_case":m.support_case.__dict__,"last_assistant_question":m.last_assistant_question,"summary":m.summary,"recent_topics":m.topic_history[-2:]}
