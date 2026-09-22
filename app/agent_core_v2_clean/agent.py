from copy import deepcopy
import re
from .memory import apply_understanding
from .scope_reconciler import reconcile_turn
from .operational_coherence import reconcile_understanding_object,apply_reopen_transition

def _closing_question(text):
 value=" ".join(str(text or "").split());found=list(re.finditer(r"¿[^?]{1,420}\?",value));return found[-1].group(0).strip() if found else None

class CleanConversationalAgent:
 def __init__(self,understanding,policy,response):self.understanding=understanding;self.policy=policy;self.response=response
 def process(self,message,memory):
  before=deepcopy(memory.to_dict());u=self.understanding.interpret(message,memory)
  u,scope_corrections,boundary=reconcile_turn(u,memory,message)
  u,events=reconcile_understanding_object(u,memory,boundary)
  corrections=list(scope_corrections)+[x.get("reason") for x in events if x.get("reason")]
  normalization=deepcopy(self.understanding.normalization or {});normalization.setdefault("structural_corrections",[]);normalization["structural_corrections"].extend(x for x in corrections if x not in normalization["structural_corrections"])
  d=self.policy.decide(u,memory);apply_understanding(memory,u);apply_reopen_transition(memory,events);a=self.response.compose(message,memory,u,d);asked=_closing_question(a.text)
  if asked:
   memory.last_assistant_question=asked
   if d.ask_one_question:memory.pending_goal.status="waiting_user";memory.pending_goal.missing_detail=d.question_target
  elif d.action not in {"redirect_scope","degraded_continue"}:memory.last_assistant_question=None
  return {"input":message,"state_before":before,"understanding":u.to_dict(),"understanding_contract":{"valid":self.understanding.contract_valid,"error":self.understanding.validation_error},"goal_update_normalization":normalization,"decision":d.to_dict(),"state_after":deepcopy(memory.to_dict()),"answer":a.to_dict(),"provider_trace":{"understanding":self.understanding.last_provider_result,"response":self.response.last_provider_result},"retrieval":{"enabled":False,"phase":"conversational_foundation"},"topic_boundary":boundary,"functional_events":events,"production_changed":False}
