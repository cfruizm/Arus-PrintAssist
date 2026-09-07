from __future__ import annotations
from dataclasses import dataclass,asdict
@dataclass
class CostRoutePlan:
 route:str;run_retrieval:bool=False;run_evidence_judge:bool=False;run_answer_llm:bool=False;initial_candidates:int=3;allow_expansion:bool=False;expansion_reason:str|None=None;deterministic_response:str|None=None;estimated_calls_avoided:int=0;reasons:list[str]|None=None
 def to_dict(self):return asdict(self)
class AdaptiveCostRouteController:
 def __init__(self,initial_candidates=3,max_candidates=6):self.initial_candidates=max(1,min(4,int(initial_candidates)));self.max_candidates=max(self.initial_candidates,min(6,int(max_candidates)))
 def plan_before_retrieval(self,d,state):
  if d.conversation_act in {"capability","social","farewell"}:return CostRoutePlan("compose_lateral",run_answer_llm=True,initial_candidates=self.initial_candidates,reasons=["natural_lateral_response_without_retrieval"])
  if d.action in {"start_escalation","continue_escalation","suspend_escalation","resume_escalation"}:return CostRoutePlan("compose_escalation",run_answer_llm=True,initial_candidates=self.initial_candidates,reasons=["reuse_canonical_escalation_state"])
  if d.action=="cancel_all":return CostRoutePlan("compose_cancel",run_answer_llm=True,initial_candidates=self.initial_candidates,reasons=["natural_cancel_response"])
  if d.action=="ask_clarification":return CostRoutePlan("compose_clarification",run_answer_llm=True,initial_candidates=self.initial_candidates,reasons=["contextual_clarification"])
  if d.action!="retrieve":return CostRoutePlan("no_document_action",estimated_calls_avoided=2,reasons=["state_only_action"])
  return CostRoutePlan("adaptive_document",True,True,True,self.initial_candidates,False,reasons=["documentation_first"])
 def plan_after_judgment(self,d,e,state):
  if not (e.get("judge") or {}).get("ok"):return CostRoutePlan("compose_unassessed",True,False,True,self.initial_candidates,False,reasons=["preserve_retrieved_context_on_judge_failure"])
  counts=e.get("counts") or {}
  if int(counts.get("direct",0)):return CostRoutePlan("compose_with_direct",True,True,True,self.initial_candidates,False,reasons=["direct_evidence"])
  if sum(int(counts.get(k,0)) for k in ["partial","conditional","contextual"]):return CostRoutePlan("compose_with_bounded_evidence",True,True,True,self.initial_candidates,False,reasons=["bounded_evidence_plus_guarded_knowledge"])
  return CostRoutePlan("compose_with_internal_knowledge",True,True,True,self.initial_candidates,False,reasons=["documentation_insufficient_use_guarded_knowledge"])
 def plan_after_expansion(self,d,e,state):return self.plan_after_judgment(d,e,state)
 def expansion_query(self,original,d,state,evidence):return original
