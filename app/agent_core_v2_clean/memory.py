from .models import ConversationMemory,TurnUnderstanding,PendingGoal
STRUCTURAL_GOAL_KEYS={"intent","status","summary","known_details","missing_detail","goal_complete","current_goal","goal_type","goal_updates","answer_to_question"}
def normalize_goal_updates(updates):
 raw=dict(updates or {});clean={str(k):str(v) for k,v in raw.items() if str(k) not in STRUCTURAL_GOAL_KEYS and str(v).strip()};return clean,sorted(set(map(str,raw))-set(clean))
def _attempt_key(v):return " ".join(str(v or "").casefold().split())
def _add(xs,v):
 v=" ".join(str(v or "").split())
 if v and v.casefold() not in {x.casefold() for x in xs}:xs.append(v)
def _record_user_facts(m,clean):
 for k,v in clean.items():m.fact_records[str(k)]={"key":str(k),"value":str(v),"origin":"user","status":"confirmed","turn":m.turn_number+1}
def apply_understanding(m,u):
 if u.degraded and not u.should_retrieve:m.turn_number+=1;return
 answering=u.user_act=="answer_to_question" and bool(m.last_assistant_question)
 if not answering and u.topic_relation in {"new_topic","independent"} and not (m.support_case.status in {"diagnosing","reopened"} and u.intent in {"troubleshooting","procedural","requirements","verification"}) and u.domain_relevance=="in_scope" and m.active_topic and u.current_goal!=m.active_topic:
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
  normalized_updates=[]
  for raw in case_updates:
   f=dict(raw or {})
   if not f.get("result"):
    for alias in ("result_detail","result_text","observed_result","result_observed"):
     if str(f.get(alias) or "").strip():f["result"]=f.get(alias);break
   if not f.get("outcome"):
    for alias in ("outcome_status","result_status","resolution_outcome","outcome_observed"):
     if str(f.get(alias) or "").strip():f["outcome"]=f.get(alias);break
   normalized_updates.append(f)
  for index,f in enumerate(normalized_updates):
   k,v=str(f.get("type") or ""),str(f.get("value") or "").strip()
   if k=="scope":k="affected_scope"
   if k=="attempted_action" and not str(f.get("result") or "").strip():
    observed=next((str(x.get("value") or "").strip() for x in normalized_updates[index+1:] if str(x.get("type") or "") in {"observation","attempt_result"} and str(x.get("value") or "").strip()),None)
    if observed:f["result"]=observed
   if k=="attempted_action" and str(f.get("outcome") or "unknown").casefold()=="unknown" and str(f.get("result") or "").strip():
    f["outcome"]="unknown"
   if k in {"symptom","reported_failure","new_case"}:
    _add(m.support_case.symptoms,v);m.support_case.status="diagnosing"
    subject=str(getattr(u,"canonical_subject",None) or (u.goal_updates or {}).get("subject") or "").strip()
    if subject and not m.support_case.subject:m.support_case.subject=subject
   elif k=="observation":
    consumed=any(str(x.get("type") or "")=="attempted_action" and _attempt_key(x.get("result"))==_attempt_key(v) for x in normalized_updates[:index])
    if not consumed:_add(m.support_case.observations,v)
    m.support_case.status="diagnosing"
   elif k=="affected_scope":m.support_case.affected_scope=v;m.support_case.status="diagnosing"
   elif k=="attempted_action":
    result=str(f.get("result") or "").strip() or None
    outcome=str(f.get("outcome") or "unknown").strip().casefold()
    if outcome not in {"resolved","improved","unchanged","worsened","unknown"}:outcome="unknown"
    existing=next((x for x in m.support_case.attempts if _attempt_key(x.get("action"))==_attempt_key(v)),None)
    if existing:
     if result:existing["result"]=result
     if outcome!="unknown" or not existing.get("outcome"):existing["outcome"]=outcome
    else:m.support_case.attempts.append({"action":v,"result":result,"outcome":outcome})
    m.support_case.status="diagnosing"
   elif k=="attempt_result":
    outcome=str(f.get("outcome") or "unknown").strip().casefold()
    if outcome not in {"resolved","improved","unchanged","worsened","unknown"}:outcome="unknown"
    if m.support_case.attempts:m.support_case.attempts[-1].update({"result":v,"outcome":outcome})
    else:m.support_case.attempts.append({"action":"previous validation","result":v,"outcome":outcome})
    m.support_case.status="diagnosing"
 m.turn_number+=1
def compact_context(m):return {"active_topic":m.active_topic,"pending_goal":m.pending_goal.__dict__,"confirmed_facts":list(m.fact_records.values()),"support_case":m.support_case.__dict__,"escalation":m.escalation.to_dict(),"last_assistant_question":m.last_assistant_question,"summary":m.summary,"recent_topics":m.topic_history[-2:]}
