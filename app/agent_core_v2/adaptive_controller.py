from __future__ import annotations
from dataclasses import dataclass,asdict
@dataclass
class CostRoutePlan:
 route:str;run_retrieval:bool=False;run_evidence_judge:bool=False;run_answer_llm:bool=False;initial_candidates:int=3;allow_expansion:bool=False;expansion_reason:str|None=None;deterministic_response:str|None=None;estimated_calls_avoided:int=0;reasons:list[str]|None=None
 def to_dict(self):return asdict(self)
class AdaptiveCostRouteController:
 def __init__(self,initial_candidates=3,max_candidates=6):self.initial_candidates=max(1,min(4,int(initial_candidates)));self.max_candidates=max(self.initial_candidates,min(8,int(max_candidates)))
 def plan_before_retrieval(self,d,state):
  if d.action=="out_of_scope" or d.intent=="out_of_scope":return CostRoutePlan("deterministic_out_of_scope",deterministic_response="Solo puedo ayudar con consultas relacionadas con el servicio de impresión y las soluciones cubiertas por este entorno.",estimated_calls_avoided=2,reasons=["no_document_pipeline"])
  if d.action=="cancel_all" or d.intent=="cancel":return CostRoutePlan("deterministic_cancel",deterministic_response="Entendido. La gestión actual fue cancelada.",estimated_calls_avoided=2,reasons=["no_document_pipeline"])
  if d.action=="resume_escalation" or d.intent=="resume":return CostRoutePlan("deterministic_resume",deterministic_response="Retomemos el escalamiento desde el último dato pendiente.",estimated_calls_avoided=2,reasons=["no_document_pipeline"])
  if d.action=="ask_clarification":return CostRoutePlan("deterministic_clarification",deterministic_response=d.clarification_question or "Necesito una precisión adicional para continuar.",estimated_calls_avoided=2,reasons=["no_document_pipeline"])
  if d.action!="retrieve":return CostRoutePlan("no_document_action",estimated_calls_avoided=2,reasons=["canonical_action_does_not_require_retrieval"])
  return CostRoutePlan("adaptive_document",True,True,True,self.initial_candidates,True,reasons=["document_action_requires_evidence"])
 def plan_after_judgment(self,d,e,state):
  c=e.get("counts") or {};direct=int(c.get("direct",0));partial=int(c.get("partial",0));conditional=int(c.get("conditional",0));contextual=int(c.get("contextual",0))
  if direct:return CostRoutePlan("compose_with_direct",True,True,True,self.initial_candidates,reasons=["direct_evidence_available"])
  if partial+conditional:return CostRoutePlan("compose_with_qualified",True,True,True,self.initial_candidates,reasons=["qualified_evidence_available"])
  if d.intent=="procedural":return CostRoutePlan("deterministic_no_procedure",True,True,False,self.initial_candidates,deterministic_response=self._procedure(state),estimated_calls_avoided=1,reasons=["no_procedural_evidence"])
  if d.intent in {"requirements","architecture","warranty"}:return CostRoutePlan("expand_specialized_retrieval",True,True,False,self.initial_candidates,True,"same_product_no_direct_evidence",reasons=["specialized_expansion"])
  if d.intent=="troubleshooting" and contextual==0:return CostRoutePlan("deterministic_diagnostic_clarification",True,True,False,self.initial_candidates,deterministic_response=self._troubleshooting(state),estimated_calls_avoided=1,reasons=["no_applicable_troubleshooting_evidence"])
  return CostRoutePlan("compose_contextual",True,True,True,self.initial_candidates,reasons=["contextual_evidence"])
 def plan_after_expansion(self,d,e,state):
  c=e.get("counts") or {}
  if int(c.get("direct",0))+int(c.get("partial",0))+int(c.get("conditional",0)):return CostRoutePlan("compose_after_expansion",True,True,True,self.max_candidates,reasons=["expansion_found_evidence"])
  return CostRoutePlan("deterministic_after_empty_expansion",True,True,False,self.max_candidates,deterministic_response=self._limit(d.intent,state),estimated_calls_avoided=1,reasons=["expansion_empty"])
 def expansion_query(self,original,d,state,evidence):
  titles=[x.get("title") for x in (evidence.get("contextual") or evidence.get("retrieved") or [])[:2]]
  return original+((". Documentos referenciados: "+"; ".join(titles)) if titles else "")
 def _names(self,state):
  names=[]
  for x in state.active_topic.products:
   name=str(getattr(x,"canonical_name","") or getattr(x,"matched_text","") or "").strip();matched=str(getattr(x,"matched_text","") or "").strip()
   names.append(matched if "_" in name and matched else name.replace("_"," ").title())
  return ", ".join(names) or "el producto indicado"
 def _procedure(self,state):return f"**Cobertura documental**\nNo encontré instrucciones directamente aplicables en {self._names(state)}.\n\n**Orientación general complementaria**\nConfirma el nombre exacto de la función u opción visible.\n\n**Restricciones y validación**\nNo es seguro inferir rutas sin una guía específica."
 def _troubleshooting(self,state):return f"**Cobertura documental**\nNo encontré evidencia directamente aplicable al caso de {self._names(state)}.\n\n**Orientación general complementaria**\nConfirma el mensaje exacto y el punto del flujo donde ocurre la falla.\n\n**Restricciones y validación**\nNo realices cambios sensibles sin documentación aplicable."
 def _limit(self,intent,state):return f"**Cobertura documental**\nLa búsqueda ampliada no encontró información directamente aplicable para {intent} en {self._names(state)}.\n\n**Restricciones y validación**\nNo se deben inferir requisitos o procedimientos sin documentación."
