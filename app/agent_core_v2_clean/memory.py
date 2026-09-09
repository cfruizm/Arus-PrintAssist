from __future__ import annotations
from .models import ConversationMemory,TurnUnderstanding,PendingGoal

def _add_unique(items,value):
 value=" ".join(str(value or "").split())
 if value and value.casefold() not in {x.casefold() for x in items}:items.append(value)

def apply_understanding(memory:ConversationMemory,u:TurnUnderstanding)->None:
 if u.topic_relation=="new_topic" and memory.active_topic:
  memory.topic_history.append({"topic":memory.active_topic,"goal":memory.pending_goal.summary,"case":memory.support_case.__dict__.copy()})
  memory.pending_goal=PendingGoal();memory.support_case=type(memory.support_case)()
 if u.topic_relation!="independent" and u.domain_relevance!="out_of_scope":
  memory.active_topic=u.current_goal or memory.active_topic
  if u.current_goal:
   memory.pending_goal.summary=u.current_goal
   memory.pending_goal.intent=u.intent
   memory.pending_goal.status="complete" if u.goal_complete else "active"
   memory.pending_goal.missing_detail=u.clarification_target if u.needs_clarification else None
  memory.pending_goal.known_details.update({str(k):str(v) for k,v in u.goal_updates.items() if str(v).strip()})
  for fact in u.case_updates:
   kind,value=str(fact.get("type") or ""),str(fact.get("value") or "").strip()
   if kind in {"symptom","reported_failure"}:_add_unique(memory.support_case.symptoms,value);memory.support_case.status="diagnosing"
   elif kind=="observation":_add_unique(memory.support_case.observations,value);memory.support_case.status="diagnosing"
   elif kind=="affected_scope":memory.support_case.affected_scope=value;memory.support_case.status="diagnosing"
   elif kind=="attempted_action":memory.support_case.attempts.append({"action":value,"result":None});memory.support_case.status="diagnosing"
   elif kind=="attempt_result":
    if memory.support_case.attempts:memory.support_case.attempts[-1]["result"]=value
    else:memory.support_case.attempts.append({"action":"previous validation","result":value})
    memory.support_case.status="diagnosing"
 memory.turn_number+=1

def compact_context(memory:ConversationMemory)->dict:
 return {"active_topic":memory.active_topic,"pending_goal":memory.pending_goal.__dict__,"support_case":memory.support_case.__dict__,"last_assistant_question":memory.last_assistant_question,"summary":memory.summary,"recent_topics":memory.topic_history[-2:]}
