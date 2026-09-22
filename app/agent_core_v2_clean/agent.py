from __future__ import annotations
from copy import deepcopy
from .models import ConversationMemory
from .understanding import ConversationUnderstanding
from .reconciler import TurnReconciler
from .memory import apply_understanding
from .retrieval import RetrievalQueryBuilder, ReadOnlyRetrieval
from .evidence import evidence_summary
from .response import ResponseComposer

class CleanConversationalAgent:
 def __init__(self,understanding,policy,response):self.understanding=understanding;self.policy=policy;self.response=response
 def process(self,message,memory):
  before=deepcopy(memory.to_dict());u=self.understanding.interpret(message,memory);u,c,b=reconcile_turn(u,memory,message);u,e=reconcile_understanding_object(u,memory,b);n=deepcopy(self.understanding.normalization or {});n.setdefault("structural_corrections",[]);n["structural_corrections"].extend(x for x in c+[z.get("reason") for z in e] if x and x not in n["structural_corrections"]);d=self.policy.decide(u,memory);apply_understanding(memory,u);apply_reopen_transition(memory,e);a=self.response.compose(message,memory,u,d);q=_closing_question(a.text)
  if q:memory.last_assistant_question=q
  elif d.action not in {"redirect_scope","degraded_continue"}:memory.last_assistant_question=None
  return {"input":message,"state_before":before,"understanding":u.to_dict(),"understanding_contract":{"valid":self.understanding.contract_valid,"error":self.understanding.validation_error,"normalization":deepcopy(self.understanding.normalization or {}),"repair_attempted":bool((self.understanding.normalization or {}).get("repair_attempted")),"repair_succeeded":bool((self.understanding.normalization or {}).get("repair_succeeded"))},"goal_update_normalization":n,"decision":d.to_dict(),"state_after":deepcopy(memory.to_dict()),"answer":a.to_dict(),"provider_trace":{"understanding":self.understanding.last_provider_result,"response":self.response.last_provider_result},"retrieval":{"enabled":False},"topic_boundary":b,"functional_events":e,"production_changed":False}
