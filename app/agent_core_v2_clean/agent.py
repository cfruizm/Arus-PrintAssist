from copy import deepcopy
from .memory import apply_understanding
class CleanConversationalAgent:
 def __init__(self,understanding,policy,response):self.understanding=understanding;self.policy=policy;self.response=response
 def process(self,message,memory):
  before=deepcopy(memory.to_dict());u=self.understanding.interpret(message,memory);d=self.policy.decide(u,memory);apply_understanding(memory,u);a=self.response.compose(message,memory,u,d)
  if d.ask_one_question:memory.last_assistant_question=a.text
  elif d.action not in {"redirect_scope","degraded_continue"}:memory.last_assistant_question=None
  return {"input":message,"state_before":before,"understanding":u.to_dict(),"decision":d.to_dict(),"state_after":deepcopy(memory.to_dict()),"answer":a.to_dict(),"provider_trace":{"understanding":self.understanding.last_provider_result,"response":self.response.last_provider_result},"retrieval":{"enabled":False,"phase":"conversational_foundation"},"production_changed":False}
