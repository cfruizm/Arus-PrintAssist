from __future__ import annotations
import json,re
class ResponseComposer:
 def __init__(self,gateway=None,max_tokens=400):self.gateway=gateway;self.max_tokens=max_tokens
 def compose(self,message,decision,state,evidence):
  direct=evidence.get("direct") or [];qualified=(evidence.get("partial") or [])+(evidence.get("conditional") or []);docs=(direct+qualified)[:3]
  if decision.action=="ask_clarification":return {"mode":"clarification","text":decision.clarification_question or "Necesito una precisión adicional para continuar.","citations":[],"knowledge_used":False}
  if decision.action!="retrieve":return {"mode":"directive","text":"","citations":[],"knowledge_used":False}
  if self.gateway is None:return {"mode":"documented_pending" if docs else "hybrid_pending","text":"Respuesta pendiente.","citations":[x["id"] for x in docs],"knowledge_used":not bool(docs)}
  from app.llm_gateway.models import LLMRequest
  sources=[]
  for x in docs:
   a=x.get("semantic_assessment") or {};sources.append({"id":x["id"],"title":x["title"],"url":x["url"],"excerpt":x["text"][:2000],"applicability":a.get("applicability"),"conditions":a.get("conditions"),"supported_claims":a.get("supported_claims")})
  products=[x.canonical_name for x in state.active_topic.products];symptoms=list(state.technical_case.symptoms);attempts=[{"action":x.action,"result":x.result} for x in state.technical_case.attempts]
  mode="documented" if direct else "hybrid_supported" if qualified else "hybrid_general"
  payload={"message":message,"intent":decision.intent,"products":products,"symptoms":symptoms,"attempts":attempts,"mode":mode,"sources":sources,"rules":["Máximo 190 palabras.","Usa una fuente solo dentro del alcance supported_claims y respetando conditions.","Una fuente partial o conditional debe presentarse con su condición, no como solución general.","Si no hay evidencia directa, separa Cobertura documental, Orientación general complementaria y Restricciones y validación.","No inventes procedimientos, funciones, menús, servicios, logs o parámetros.","Para procedimientos sin evidencia directa, no describas cómo suele hacerse en otros productos.","Cita solo sources con [S#].","No añadas una sección Fuentes; la interfaz formateará enlaces."]}
  r=self.gateway.complete(LLMRequest([{"role":"system","content":"Compón soporte natural y útil. Respeta estrictamente el alcance semántico de cada fuente."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,default=str)}],"agent_core_v2_answer",self.max_tokens,0.,None))
  if not r.ok or r.finish_reason=="length":return {"mode":"safe_fallback","text":self._fallback(decision.intent,products,symptoms),"citations":[],"knowledge_used":False,"finish_reason":r.finish_reason}
  text=r.text.strip();used=set(re.findall(r"\[(S\d+)\]",text));valid={x["id"] for x in sources}
  if used-valid:return {"mode":"safe_fallback","text":self._fallback(decision.intent,products,symptoms),"citations":[],"knowledge_used":False,"reason":"unknown_citation"}
  # Direct evidence need not all be cited, but every used citation must be semantically approved.
  return {"mode":mode,"text":text,"citations":sorted(used),"knowledge_used":mode!="documented" or "Orientación general complementaria" in text,"provider":r.provider,"model":r.model,"usage":r.usage,"finish_reason":r.finish_reason}
 def _fallback(self,intent,products,symptoms):
  product=", ".join(products) or "el producto indicado"
  if intent=="procedural":return f"Cobertura documental\nNo encontré evidencia directa para confirmar este procedimiento en {product}.\n\nOrientación general complementaria\nConfirma el nombre exacto de la función o la opción visible. No es seguro inferir que exista ni proponer una ruta de configuración.\n\nRestricciones y validación\nNo conviertas documentos relacionados en instrucciones sin respaldo directo."
  return f"Cobertura documental\nNo encontré evidencia directa suficiente para el caso en {product}.\n\nOrientación general complementaria\nConfirma en qué punto ocurre el síntoma y el mensaje exacto. Esta orientación no representa un procedimiento documentado.\n\nRestricciones y validación\nNo realices cambios sensibles sin documentación aplicable."
