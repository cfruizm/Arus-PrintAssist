from __future__ import annotations
from dataclasses import dataclass,asdict
@dataclass
class CostRoutePlan:
 route:str;run_retrieval:bool=False;run_evidence_judge:bool=False;run_answer_llm:bool=False;initial_candidates:int=3;allow_expansion:bool=False;expansion_reason:str|None=None;deterministic_response:str|None=None;estimated_calls_avoided:int=0;reasons:list[str]|None=None
 def to_dict(self):return asdict(self)
class AdaptiveCostRouteController:
 def __init__(self,initial_candidates=3,max_candidates=6):self.initial_candidates=max(1,min(4,int(initial_candidates)));self.max_candidates=max(self.initial_candidates,min(6,int(max_candidates)))
 def plan_before_retrieval(self,d,state):
  if d.conversation_act=="capability":return CostRoutePlan("deterministic_capability",deterministic_response="Puedo ayudarte a diagnosticar incidentes de impresión, consultar documentación técnica, complementar con orientación general identificada, registrar pruebas y resultados, cambiar de tema y preparar un escalamiento con la información recopilada.",estimated_calls_avoided=2,reasons=["capability_is_non_documental"])
  if d.conversation_act=="farewell":return CostRoutePlan("deterministic_farewell",deterministic_response="Hasta luego. Cuando necesites continuar con un caso de impresión, aquí estaré.",estimated_calls_avoided=2,reasons=["farewell_is_non_documental"])
  if d.conversation_act=="social":return CostRoutePlan("deterministic_social",deterministic_response="Hola. Cuéntame en qué caso de impresión necesitas apoyo.",estimated_calls_avoided=2,reasons=["social_is_non_documental"])
  if d.action=="out_of_scope" or d.intent=="out_of_scope":return CostRoutePlan("deterministic_out_of_scope",deterministic_response="Puedo ayudarte con soporte de impresión, documentación técnica y escalamiento de incidentes.",estimated_calls_avoided=2,reasons=["out_of_scope"])
  if d.action=="cancel_all":return CostRoutePlan("deterministic_cancel",deterministic_response="Entendido. Cerré el flujo actual.",estimated_calls_avoided=2,reasons=["cancel"])
  if d.action=="ask_clarification":return CostRoutePlan("deterministic_clarification",deterministic_response=d.clarification_question or "Necesito una precisión adicional para continuar.",estimated_calls_avoided=2,reasons=["clarification"])
  if d.action!="retrieve":return CostRoutePlan("no_document_action",estimated_calls_avoided=2,reasons=["no_retrieval_action"])
  return CostRoutePlan("adaptive_document",True,True,True,self.initial_candidates,False,reasons=["valid_document_request"])
 def plan_after_judgment(self,d,e,state):
  judge=e.get("judge") or {};counts=e.get("counts") or {}
  if not judge.get("ok"):return CostRoutePlan("compose_unassessed",True,False,True,self.initial_candidates,False,reasons=["judge_failed_preserve_candidates"])
  if int(counts.get("direct",0)):return CostRoutePlan("compose_with_direct",True,True,True,self.initial_candidates,False,reasons=["direct_evidence"])
  if int(counts.get("partial",0))+int(counts.get("conditional",0))+int(counts.get("contextual",0)):return CostRoutePlan("compose_with_context",True,True,True,self.initial_candidates,False,reasons=["bounded_or_contextual_evidence"])
  return CostRoutePlan("compose_without_evidence",True,True,True,self.initial_candidates,False,reasons=["knowledge_complement_allowed"])
 def plan_after_expansion(self,d,e,state):return self.plan_after_judgment(d,e,state)
 def expansion_query(self,original,d,state,evidence):return original
