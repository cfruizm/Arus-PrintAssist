from copy import deepcopy
import re
from .memory import apply_understanding

def _closing_question(text):
 value=" ".join(str(text or "").split())
 found=list(re.finditer(r"¿[^?]{1,420}\?",value))
 return found[-1].group(0).strip() if found else None

class CleanConversationalAgent:
 def __init__(self,understanding,policy,response):self.understanding=understanding;self.policy=policy;self.response=response
 def process(self,message,memory):
  before=deepcopy(memory.to_dict());u=self.understanding.interpret(message,memory);d=self.policy.decide(u,memory);apply_understanding(memory,u);a=self.response.compose(message,memory,u,d)
  asked=_closing_question(a.text)
  if asked:
   memory.last_assistant_question=asked
   if d.ask_one_question:
    memory.pending_goal.status="waiting_user";memory.pending_goal.missing_detail=d.question_target
  elif d.action not in {"redirect_scope","degraded_continue"}:
   memory.last_assistant_question=None
   if memory.pending_goal.status=="waiting_user":memory.pending_goal.status="active";memory.pending_goal.missing_detail=None
  return {"input":message,"state_before":before,"understanding":u.to_dict(),"understanding_contract":{"valid":self.understanding.contract_valid,"error":self.understanding.validation_error},"goal_update_normalization":self.understanding.normalization,"decision":d.to_dict(),"state_after":deepcopy(memory.to_dict()),"answer":a.to_dict(),"provider_trace":{"understanding":self.understanding.last_provider_result,"response":self.response.last_provider_result},"retrieval":{"enabled":False,"phase":"conversational_foundation"},"production_changed":False}
