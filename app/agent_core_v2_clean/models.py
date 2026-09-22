from __future__ import annotations
from copy import deepcopy

def _json_value(value):
 if isinstance(value,_Record):return {str(k):_json_value(v) for k,v in value.__dict__.items()}
 if isinstance(value,dict):return {str(k):_json_value(v) for k,v in value.items()}
 if isinstance(value,(list,tuple,set)):return [_json_value(v) for v in value]
 if value is None or isinstance(value,(str,int,float,bool)):return value
 return str(value)

class _Record:
 def to_dict(self):return _json_value(self)

class PendingGoal(_Record):
 def __init__(self,summary="",intent="unknown",known_details=None,missing_detail=None,status="inactive"):
  self.summary=str(summary or "");self.intent=str(intent or "unknown");self.known_details=dict(known_details or {});self.missing_detail=missing_detail;self.status=str(status or "inactive")
 def is_open(self):return self.status in {"active","waiting_user","partially_answered","blocked_by_evidence"}

class SupportCase(_Record):
 def __init__(self,status="idle",symptoms=None,observations=None,attempts=None,affected_scope=None,resolution_status=None):
  self.status=str(status or "idle");self.symptoms=list(symptoms or []);self.observations=list(observations or []);self.attempts=list(attempts or []);self.affected_scope=affected_scope;self.resolution_status=resolution_status

class ConversationMemory(_Record):
 def __init__(self,conversation_id="v2-clean-lab",active_topic=None,pending_goal=None,support_case=None,last_assistant_question=None,summary="",turn_number=0,topic_history=None,fact_records=None):
  self.conversation_id=str(conversation_id or "v2-clean-lab");self.active_topic=active_topic;self.pending_goal=pending_goal if isinstance(pending_goal,PendingGoal) else PendingGoal(**(pending_goal or {}));self.support_case=support_case if isinstance(support_case,SupportCase) else SupportCase(**(support_case or {}));self.last_assistant_question=last_assistant_question;self.summary=str(summary or "");self.turn_number=int(turn_number or 0);self.topic_history=list(topic_history or []);self.fact_records=dict(fact_records or {})

class TurnUnderstanding(_Record):
 def __init__(self,user_act,intent,topic_relation,domain_relevance,current_goal,goal_complete,goal_updates=None,case_updates=None,needs_clarification=False,clarification_target=None,should_retrieve=False,confidence=0.,reasoning_summary="",degraded=False):
  self.user_act=str(user_act or "unknown");self.intent=str(intent or "unknown");self.topic_relation=str(topic_relation or "new_topic");self.domain_relevance=str(domain_relevance or "uncertain");self.current_goal=str(current_goal or "");self.goal_complete=bool(goal_complete);self.goal_updates=dict(goal_updates or {});self.case_updates=list(case_updates or []);self.needs_clarification=bool(needs_clarification);self.clarification_target=clarification_target;self.should_retrieve=bool(should_retrieve);self.confidence=float(confidence or 0.);self.reasoning_summary=str(reasoning_summary or "");self.degraded=bool(degraded)

class AgentDecision(_Record):
 def __init__(self,action,reason,ask_one_question=False,question_target=None):self.action=str(action);self.reason=str(reason);self.ask_one_question=bool(ask_one_question);self.question_target=question_target

class AgentResponse(_Record):
 def __init__(self,text,mode,knowledge_used=False,provider=None,model=None,usage=None,finish_reason=None):self.text=str(text or "");self.mode=str(mode);self.knowledge_used=bool(knowledge_used);self.provider=provider;self.model=model;self.usage=dict(usage or {});self.finish_reason=finish_reason
