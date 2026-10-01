import json
from pathlib import Path
from .models import ConversationMemory
from .understanding import ConversationUnderstanding

class Result:
 def __init__(self,text):
  self.ok=True;self.text=text;self.error_code=None
 def to_dict(self):return {"ok":True,"text":self.text}
class Gateway:
 def __init__(self,text):self.text=text;self.calls=0
 def complete(self,request):self.calls+=1;return Result(self.text)

def normalize(raw,memory):
 gateway=Gateway(json.dumps(raw,ensure_ascii=False))
 engine=ConversationUnderstanding(gateway,220)
 return engine.interpret("fixture",memory),engine,gateway

def base(**overrides):
 value={
  "canonical_subject":"Active platform","case_updates":[],"clarification_target":None,
  "confidence":0.95,"current_goal":"Close completed interaction","domain_relevance":"in_scope",
  "goal_complete":True,"goal_updates":{"goal_status":"completed","subject":"Active platform"},
  "intent":"requirements","needs_clarification":False,"reasoning_summary":"Completed acknowledgement",
  "reference_relation":"current_subject","requested_workflow":"none","should_retrieve":False,
  "subject_origin":"conversation_memory","topic_relation":"same_topic","user_act":"answer_to_question",
 }
 value.update(overrides);return value

def run(runtime_json):
 data=json.loads(Path(runtime_json).read_text(encoding="utf-8"))
 observed=json.loads(data["turns"][-1]["provider_trace"]["understanding"]["text"])
 memory=ConversationMemory(active_topic="Technical topic",active_subject="Active platform")
 social,engine,gateway=normalize(observed,memory)
 pending=ConversationMemory(active_topic="Technical topic",active_subject="Active platform",last_assistant_question="Confirm result?")
 answer,_,_=normalize(base(),pending)
 case_fact,_,_=normalize(base(case_updates=[{"type":"attempt_result","value":"completed"}]),memory)
 workflow,_,_=normalize(base(requested_workflow="confirm_escalation"),memory)
 retrieval,_,_=normalize(base(should_retrieve=True),memory)
 new_detail,_,_=normalize(base(goal_updates={"goal_status":"completed","subject":"Active platform","operation":"review logs"}),memory)
 checks={
  "exact_runtime_closure_becomes_social":social.user_act=="social" and social.intent=="social",
  "exact_runtime_closure_disables_retrieval":social.should_retrieve is False,
  "inherited_subject_removed_from_social_turn":social.canonical_subject is None and social.reference_relation=="none",
  "single_understanding_call":gateway.calls==1,
  "structured_correction_recorded":"semantic_non_operational_closure_recovered_before_followup_policy" in engine.normalization.get("structural_corrections",[]),
  "pending_question_not_swallowed":answer.user_act!="social" and answer.intent!="social",
  "case_fact_not_swallowed":case_fact.user_act!="social" and case_fact.intent!="social",
  "workflow_not_swallowed":workflow.user_act!="social" and workflow.intent!="social",
  "retrieval_turn_not_swallowed":retrieval.user_act!="social" and retrieval.intent!="social",
  "new_technical_detail_not_swallowed":new_detail.user_act!="social" and new_detail.intent!="social",
 }
 failed=[k for k,v in checks.items() if not v]
 return {"phase":"4B.1.9","passed":len(checks)-len(failed),"failed":len(failed),"checks":checks,"normalized_runtime_closure":social.to_dict()}
if __name__=="__main__":
 import sys
 result=run(sys.argv[1]);print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(1 if result["failed"] else 0)
