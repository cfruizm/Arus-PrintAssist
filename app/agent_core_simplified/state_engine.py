from __future__ import annotations
from copy import deepcopy
from .models import *
def norm(v):return " ".join(str(v or "").casefold().split())
def add_unique(xs,v):
 if v and not any(norm(x)==norm(v) for x in xs):xs.append(v)
def archive(state):
 if state.active_topic.products or state.case.symptoms or state.case.details or state.case.attempts:state.topic_history.append({"topic":deepcopy(state.active_topic),"case":deepcopy(state.case)})
def apply_plan(state,plan,resolve_entities):
 state.turn_number+=1;audit=[]
 if plan.topic_relation=="new":archive(state);state.active_topic=Topic(f"topic-{state.turn_number}");state.case=Case();audit.append("new_topic")
 elif plan.topic_relation=="previous" and state.topic_history:
  current={"topic":deepcopy(state.active_topic),"case":deepcopy(state.case)};old=state.topic_history.pop();state.topic_history.append(current);state.active_topic=old["topic"];state.case=old["case"];audit.append("restore_previous")
 for e in resolve_entities(plan.entities):
  target=state.active_topic.products if e.kind=="product" else state.active_topic.components if e.kind=="component" else state.active_topic.processes
  if not any(x.canonical_id==e.canonical_id and x.kind==e.kind for x in target):target.append(e);audit.append("entity:"+e.canonical_id)
 for s in plan.symptoms:add_unique(state.case.symptoms,s);state.case.status="diagnosing";audit.append("symptom")
 for d in plan.details:
  if d not in state.case.details:state.case.details.append(d);audit.append("detail:"+d.get("type","detail"))
  if d.get("type")=="scope":state.case.affected_scope=d.get("value")
 if plan.attempt:
  state.case.attempts.append(Attempt(plan.attempt));state.case.status="diagnosing";audit.append("attempt")
 if plan.attempt_result:
  if state.case.attempts:state.case.attempts[-1].result=plan.attempt_result;state.case.status=state.case.resolution_status="unresolved";audit.append("attempt_result")
  else:state.case.details.append({"type":"unlinked_attempt_result","value":plan.attempt_result});audit.append("unlinked_attempt_result")
 state.active_topic.request_kind=plan.request_kind
 if plan.escalation_action=="start":state.escalation.status="collecting";audit.append("escalation_start")
 elif plan.escalation_action=="finish":state.escalation.status="completed";audit.append("escalation_finish")
 elif plan.escalation_action=="cancel":state.escalation=Escalation(status="cancelled");audit.append("escalation_cancel")
 return audit
