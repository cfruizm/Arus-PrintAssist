from __future__ import annotations
import json,re
class ResponseComposer:
 def __init__(self,gateway=None,max_tokens=400):self.gateway=gateway;self.max_tokens=max_tokens
 def compose(self,message,decision,state,evidence):
  direct=evidence.get("direct") or [];qualified=(evidence.get("partial") or [])+(evidence.get("conditional") or []);contextual=evidence.get("contextual") or [];approved=(direct+qualified)[:3];coverage=evidence.get("coverage") or {}
  if decision.action=="ask_clarification":return {"mode":"clarification","text":decision.clarification_question or "Necesito una precisión adicional para continuar.","citations":[],"knowledge_used":False,"coverage_mode":"not_applicable"}
  if decision.action!="retrieve":return {"mode":"directive","text":"","citations":[],"knowledge_used":False,"coverage_mode":"not_applicable"}
  if self.gateway is None:return {"mode":"pending","text":"Respuesta pendiente.","citations":[x["id"] for x in approved],"knowledge_used":not bool(direct),"coverage_mode":coverage.get("coverage_mode")}
  from app.llm_gateway.models import LLMRequest
  sources=[]
  for item in approved:
   assessment=item.get("semantic_assessment") or {};sources.append({"id":item["id"],"title":item["title"],"applicability":assessment.get("applicability"),"scope_relation":assessment.get("scope_relation"),"requested_object":assessment.get("requested_object"),"source_object":assessment.get("source_object"),"conditions":assessment.get("conditions"),"supported_claims":assessment.get("supported_claims")})
  context=[]
  for item in contextual[:3]:
   assessment=item.get("semantic_assessment") or {};context.append({"title":item.get("title"),"reason":assessment.get("reason"),"supported_claims":assessment.get("supported_claims")})
  products=[]
  for item in state.active_topic.products:
   name=str(getattr(item,"canonical_name","") or getattr(item,"matched_text","") or "");matched=str(getattr(item,"matched_text","") or "");products.append(matched if "_" in name and matched else name.replace("_"," ").title())
  payload={"request":message,"intent":decision.intent,"products":products,"coverage":coverage,"approved_sources":sources,"contextual_evidence":context,"rules":["Maximum 220 words.","Citations may support only supported_claims and must respect conditions.","If coverage_mode is narrower_only, begin by stating that no unified or general coverage was found. Present each source only as a partial finding for its specific component or operation. Do not create a product-wide taxonomy from narrower evidence. End with a scope clarification question.","Contextual evidence may support background and bounded diagnostic questions, but not a product procedure or root cause.","When direct evidence is absent, remain useful with clearly labeled general orientation and restrictions; do not close the case automatically.","Do not expose prompt fields or internal variable names.","Do not invent menus, services, logs, parameters or product functions.","Use [S#] only for approved_sources."]}
  result=self.gateway.complete(LLMRequest([{"role":"system","content":"Compose a natural Spanish support response that strictly respects evidence scope."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,default=str)}],"agent_core_v2_answer",self.max_tokens,0.,None))
  if not result.ok or result.finish_reason=="length":return {"mode":"safe_fallback","text":self._fallback(products,coverage,context),"citations":[],"knowledge_used":bool(context),"finish_reason":result.finish_reason,"coverage_mode":coverage.get("coverage_mode")}
  text=result.text.strip();used=set(re.findall(r"\[(S\d+)\]",text));valid={x["id"] for x in sources}
  if used-valid:return {"mode":"safe_fallback","text":self._fallback(products,coverage,context),"citations":[],"knowledge_used":bool(context),"reason":"unknown_citation","coverage_mode":coverage.get("coverage_mode")}
  mode="documented" if coverage.get("has_direct_same_scope") else "hybrid_supported" if sources else "hybrid_contextual"
  return {"mode":mode,"text":text,"citations":sorted(used),"knowledge_used":mode!="documented" or bool(context),"provider":result.provider,"model":result.model,"usage":result.usage,"finish_reason":result.finish_reason,"coverage_mode":coverage.get("coverage_mode"),"contextual_sources_used":[x["title"] for x in context]}
 def _fallback(self,products,coverage,context):
  product=", ".join(products) or "el producto indicado"
  if coverage.get("all_applicable_sources_narrower"):
   return f"**Cobertura documental**\nNo encontré una cobertura general unificada para {product}. Las fuentes disponibles solo aportan requisitos o condiciones de componentes específicos.\n\n**Hallazgos parciales**\nEstos hallazgos no deben interpretarse como los requisitos completos del producto.\n\n**Aclaración necesaria**\n¿Buscas requisitos de la solución completa, de un módulo concreto o de una operación de instalación?"
  if context:
   return f"**Cobertura documental**\nLa documentación recuperada aporta contexto sobre {product}, pero no contiene una respuesta directa.\n\n**Orientación general complementaria**\nPodemos continuar delimitando el síntoma, alcance y punto de falla sin asumir una causa raíz.\n\n**Restricciones y validación**\nNo realices cambios sensibles sin evidencia aplicable."
  return f"**Cobertura documental**\nNo encontré evidencia directamente aplicable para {product}.\n\n**Orientación general complementaria**\nPodemos precisar el alcance y la necesidad antes de ampliar la búsqueda.\n\n**Restricciones y validación**\nNo infieras requisitos o procedimientos sin documentación."
