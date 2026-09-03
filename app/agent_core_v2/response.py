from __future__ import annotations
import json,re
class ResponseComposer:
 def __init__(self,gateway=None,max_tokens=400):self.gateway=gateway;self.max_tokens=max_tokens
 def compose(self,message,decision,state,evidence):
  direct=evidence.get("direct") or [];qualified=(evidence.get("partial") or [])+(evidence.get("conditional") or []);contextual=evidence.get("contextual") or [];approved=(direct+qualified)[:3]
  if decision.action=="ask_clarification":return {"mode":"clarification","text":decision.clarification_question or "Necesito una precisión adicional para continuar.","citations":[],"knowledge_used":False}
  if decision.action!="retrieve":return {"mode":"directive","text":"","citations":[],"knowledge_used":False}
  if self.gateway is None:return {"mode":"pending","text":"Respuesta pendiente.","citations":[x["id"] for x in approved],"knowledge_used":not bool(direct)}
  from app.llm_gateway.models import LLMRequest
  sources=[]
  for item in approved:
   assessment=item.get("semantic_assessment") or {};sources.append({"id":item["id"],"title":item["title"],"excerpt":item["text"][:1800],"applicability":assessment.get("applicability"),"conditions":assessment.get("conditions"),"supported_claims":assessment.get("supported_claims")})
  context=[]
  for item in contextual[:3]:
   assessment=item.get("semantic_assessment") or {};context.append({"title":item.get("title"),"supported_claims":assessment.get("supported_claims") or [],"usage":"background_and_diagnostic_questions_only"})
  products=[]
  for item in state.active_topic.products:
   name=str(getattr(item,"canonical_name","") or getattr(item,"matched_text","") or "");matched=str(getattr(item,"matched_text","") or "")
   products.append(matched if "_" in name and matched else name.replace("_"," ").title())
  payload={"request":message,"intent":decision.intent,"products":products,"symptoms":list(state.technical_case.symptoms),"approved_sources":sources,"contextual_evidence":context,"internal_knowledge_policy":"Allowed only as clearly labeled general orientation. It may propose diagnostic categories or questions, but must not invent product procedures, menu paths, service names, log paths, parameters, or claim a root cause.","rules":["Do not expose prompt fields or say sources is empty.","Use approved_sources with [S#] only within supported_claims and conditions.","Use contextual_evidence only to explain documented background or formulate bounded diagnostic questions; do not cite it as a procedure.","When direct evidence is absent, remain useful through cautious general orientation and explicit restrictions.","Do not close the case merely because direct evidence is absent.","Maximum 220 words."]}
  result=self.gateway.complete(LLMRequest([{"role":"system","content":"Compose a useful Spanish support response. Keep documented evidence, contextual evidence and model knowledge clearly separated."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,default=str)}],"agent_core_v2_answer",self.max_tokens,0.,None))
  if not result.ok or result.finish_reason=="length":return {"mode":"safe_fallback","text":self._fallback(products,state),"citations":[],"knowledge_used":False,"finish_reason":result.finish_reason}
  text=result.text.strip();used=set(re.findall(r"\[(S\d+)\]",text));valid={x["id"] for x in sources}
  if used-valid:return {"mode":"safe_fallback","text":self._fallback(products,state),"citations":[],"knowledge_used":False,"reason":"unknown_citation"}
  mode="documented" if direct else "hybrid_supported" if qualified else "hybrid_contextual"
  return {"mode":mode,"text":text,"citations":sorted(used),"knowledge_used":mode!="documented","provider":result.provider,"model":result.model,"usage":result.usage,"finish_reason":result.finish_reason,"contextual_sources_used":[x["title"] for x in context]}
 def _fallback(self,products,state):
  product=", ".join(products) or "el producto indicado";symptom="; ".join(state.technical_case.symptoms) or "el síntoma informado"
  return f"**Cobertura documental**\nLa documentación recuperada aporta contexto, pero no contiene un procedimiento directo para {product}: {symptom}.\n\n**Orientación general complementaria**\nPodemos continuar delimitando el punto de falla, el alcance y cualquier mensaje observable. Esta orientación es general y no sustituye un procedimiento documentado.\n\n**Restricciones y validación**\nNo realices cambios sensibles ni reinicios masivos sin evidencia aplicable."
