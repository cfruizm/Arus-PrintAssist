from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Any

NO_RETRIEVAL_ACTIONS={"out_of_scope","respond_directly","cancel_all","resume_escalation","start_escalation","continue_escalation","suspend_escalation","record_case_detail","record_attempt","record_attempt_result","ask_clarification"}
DETERMINISTIC_INTENTS={"out_of_scope","cancel","resume","social","capabilities"}

@dataclass
class CostRoutePlan:
 route:str
 run_retrieval:bool=False
 run_evidence_judge:bool=False
 run_answer_llm:bool=False
 initial_candidates:int=3
 allow_expansion:bool=False
 expansion_reason:str|None=None
 deterministic_response:str|None=None
 estimated_calls_avoided:int=0
 reasons:list[str]|None=None
 def to_dict(self):return asdict(self)

class AdaptiveCostRouteController:
 def __init__(self,initial_candidates=3,max_candidates=6):
  self.initial_candidates=max(1,min(4,int(initial_candidates)));self.max_candidates=max(self.initial_candidates,min(8,int(max_candidates)))
 def plan_before_retrieval(self,decision,state)->CostRoutePlan:
  action=str(decision.action);intent=str(decision.intent);reasons=[]
  if action=="out_of_scope" or intent=="out_of_scope":
   return CostRoutePlan("deterministic_out_of_scope",deterministic_response="Solo puedo ayudar con consultas relacionadas con el servicio de impresión y las soluciones cubiertas por este entorno. Si tienes un caso de impresión, indícame el producto, proceso o síntoma.",estimated_calls_avoided=2,reasons=["out_of_scope_requires_no_document_pipeline"])
  if action=="cancel_all" or intent=="cancel":
   return CostRoutePlan("deterministic_cancel",deterministic_response="Entendido. La gestión actual fue cancelada y el contexto activo quedó cerrado.",estimated_calls_avoided=2,reasons=["cancel_requires_no_document_pipeline"])
  if action=="resume_escalation" or intent=="resume":
   return CostRoutePlan("deterministic_resume",deterministic_response="Retomemos el escalamiento desde el último dato pendiente.",estimated_calls_avoided=2,reasons=["resume_requires_no_document_pipeline"])
  if action=="ask_clarification":
   return CostRoutePlan("deterministic_clarification",deterministic_response=decision.clarification_question or "Necesito una precisión adicional para continuar.",estimated_calls_avoided=2,reasons=["clarification_requires_no_document_pipeline"])
  if action!="retrieve":
   return CostRoutePlan("no_document_action",estimated_calls_avoided=2,reasons=["canonical_action_does_not_require_retrieval"])
  return CostRoutePlan("adaptive_document",True,True,True,self.initial_candidates,True,None,None,0,["document_action_requires_evidence"])
 def plan_after_judgment(self,decision,evidence,state)->CostRoutePlan:
  counts=evidence.get("counts") or {};direct=int(counts.get("direct",0));partial=int(counts.get("partial",0));conditional=int(counts.get("conditional",0));contextual=int(counts.get("contextual",0));intent=str(decision.intent)
  if direct>0:
   return CostRoutePlan("compose_with_direct",True,True,True,self.initial_candidates,False,reasons=["direct_evidence_available"])
  if partial+conditional>0:
   return CostRoutePlan("compose_with_qualified",True,True,True,self.initial_candidates,False,reasons=["qualified_evidence_available"])
  if intent=="procedural":
   text=self._procedural_without_evidence(state)
   return CostRoutePlan("deterministic_no_procedure",True,True,False,self.initial_candidates,False,deterministic_response=text,estimated_calls_avoided=1,reasons=["no_direct_or_qualified_procedural_evidence"])
  if intent in {"requirements","architecture","warranty"}:
   return CostRoutePlan("expand_specialized_retrieval",True,True,False,self.initial_candidates,True,"same_product_no_direct_evidence",None,0,["specialized_intent_benefits_from_one_expansion"])
  if intent=="troubleshooting" and contextual==0:
   text=self._troubleshooting_without_evidence(state)
   return CostRoutePlan("deterministic_diagnostic_clarification",True,True,False,self.initial_candidates,False,deterministic_response=text,estimated_calls_avoided=1,reasons=["no_applicable_troubleshooting_evidence"])
  return CostRoutePlan("compose_contextual",True,True,True,self.initial_candidates,False,reasons=["contextual_evidence_may_support_bounded_answer"])
 def plan_after_expansion(self,decision,evidence,state)->CostRoutePlan:
  counts=evidence.get("counts") or {}
  if int(counts.get("direct",0))+int(counts.get("partial",0))+int(counts.get("conditional",0))>0:
   return CostRoutePlan("compose_after_expansion",True,True,True,self.max_candidates,False,reasons=["expansion_found_applicable_evidence"])
  return CostRoutePlan("deterministic_after_empty_expansion",True,True,False,self.max_candidates,False,deterministic_response=self._intent_limit(decision.intent,state),estimated_calls_avoided=1,reasons=["expansion_found_no_applicable_evidence"])
 def expansion_query(self,original,decision,state,evidence):
  product=", ".join(getattr(x,"canonical_name",str(x)) for x in state.active_topic.products);process=", ".join(getattr(x,"canonical_name",str(x)) for x in state.active_topic.processes);titles=[x.get("title") for x in (evidence.get("contextual") or evidence.get("retrieved") or [])[:2]]
  return " | ".join(x for x in [product,str(decision.intent),process,original,"referenced manuals: "+"; ".join(titles) if titles else ""] if x)
 def _procedural_without_evidence(self,state):
  product=", ".join(getattr(x,"canonical_name",str(x)) for x in state.active_topic.products) or "el producto indicado";process=", ".join(getattr(x,"canonical_name",str(x)) for x in state.active_topic.processes) or "el procedimiento solicitado"
  return f"**Cobertura documental**\nNo encontré instrucciones directamente aplicables para {process} en {product}.\n\n**Orientación general complementaria**\nPara precisar la búsqueda, confirma el nombre exacto de la función u opción visible y el resultado que esperas obtener.\n\n**Restricciones y validación**\nNo es seguro inferir que la función exista ni proponer rutas de configuración sin una guía específica."
 def _troubleshooting_without_evidence(self,state):
  product=", ".join(getattr(x,"canonical_name",str(x)) for x in state.active_topic.products) or "el producto indicado";symptom="; ".join(state.technical_case.symptoms) or "el síntoma informado"
  return f"**Cobertura documental**\nNo encontré evidencia directamente aplicable al caso de {product}: {symptom}.\n\n**Orientación general complementaria**\nConfirma el mensaje exacto y el punto del flujo donde ocurre la falla para orientar una búsqueda más precisa.\n\n**Restricciones y validación**\nNo realices cambios sensibles sin documentación aplicable."
 def _intent_limit(self,intent,state):
  product=", ".join(getattr(x,"canonical_name",str(x)) for x in state.active_topic.products) or "el producto indicado"
  return f"**Cobertura documental**\nLa búsqueda ampliada no encontró información directamente aplicable para {intent} en {product}.\n\n**Orientación general complementaria**\nEs necesario confirmar la versión, modalidad de implementación y alcance requerido para refinar la consulta.\n\n**Restricciones y validación**\nNo se deben inferir requisitos, dependencias o procedimientos que no estén respaldados por documentación."
