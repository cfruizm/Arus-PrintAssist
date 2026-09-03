from __future__ import annotations
import json,re
class ResponseComposer:
 def __init__(self,gateway=None,max_tokens=400):self.gateway=gateway;self.max_tokens=max_tokens
 def compose(self,message,decision,state,evidence):
  citable=evidence.get("citable") or [];eligible=evidence.get("eligible") or []
  if decision.action=="ask_clarification":return {"mode":"clarification","text":decision.clarification_question or "Necesito una precisión adicional para continuar.","citations":[],"knowledge_used":False}
  if decision.action!="retrieve":return {"mode":"directive","text":"","citations":[],"knowledge_used":False}
  if self.gateway is None:
   return {"mode":"documented" if citable else "hybrid_pending","text":"Respuesta pendiente del compositor LLM.","citations":[x["id"] for x in citable],"knowledge_used":not bool(citable)}
  from app.llm_gateway.models import LLMRequest
  docs=[{"id":x["id"],"title":x["title"],"url":x["url"],"text":x["text"][:2400]} for x in citable[:3]]
  product_names=[x.canonical_name for x in state.active_topic.products]
  symptoms=list(state.technical_case.symptoms)
  attempts=[{"action":x.action,"result":x.result} for x in state.technical_case.attempts]
  mode="documented" if docs else "hybrid_general"
  rules=["Responde en español y máximo 220 palabras.","No inventes rutas de menú, servicios, logs, parámetros ni procedimientos específicos.","No menciones acciones fallidas si attempts está vacío.","No repitas acciones con result failed.","Si usas conocimiento general, identifícalo claramente como orientación complementaria y no lo cites como documentación.","Las citas [S#] solo pueden respaldar contenido tomado de sources."]
  if docs:
   structure=["Información respaldada por documentación con citas","Cobertura documental","Orientación general complementaria solo si hace falta","Restricciones y validación","Fuentes"]
  else:
   structure=["Cobertura documental: indicar que las fuentes recuperadas no responden directamente","Orientación general complementaria: formular preguntas diagnósticas seguras o categorías generales","Restricciones y validación: advertir qué no debe cambiarse sin documentación"]
  prompt={"message":message,"intent":decision.intent,"products":product_names,"symptoms":symptoms,"attempts":attempts,"retrieved_but_not_citable_titles":[x.get("title") for x in eligible[:3]],"sources":docs,"mode":mode,"required_structure":structure,"rules":rules}
  r=self.gateway.complete(LLMRequest([{"role":"system","content":"Eres el compositor controlado de Agent Core v2. Separa estrictamente documentación y conocimiento general."},{"role":"user","content":json.dumps(prompt,ensure_ascii=False,default=str)}],"agent_core_v2_answer",self.max_tokens,0.,None))
  if not r.ok:return {"mode":"provider_error","text":self._safe_fallback(decision.intent,product_names,symptoms,attempts),"citations":[],"knowledge_used":False}
  text=r.text.strip();used=set(re.findall(r"\[(S\d+)\]",text));valid={x["id"] for x in docs}
  if used-valid:return {"mode":"invalid_citations","text":self._safe_fallback(decision.intent,product_names,symptoms,attempts),"citations":[],"knowledge_used":False}
  if docs and not used:return {"mode":"missing_citations","text":self._safe_fallback(decision.intent,product_names,symptoms,attempts),"citations":[],"knowledge_used":False}
  return {"mode":mode,"text":text,"citations":sorted(used),"knowledge_used":not bool(docs) or "Orientación general complementaria" in text,"provider":r.provider,"model":r.model,"usage":r.usage}
 def _safe_fallback(self,intent,products,symptoms,attempts):
  product=", ".join(products) or "el producto indicado";symptom="; ".join(symptoms) or "el síntoma informado";failed=[x["action"] for x in attempts if x.get("result")=="failed"]
  if intent=="procedural":return f"Cobertura documental\nNo se encontraron pasos directamente aplicables para el procedimiento en {product}.\n\nRestricciones y validación\nNo se deben convertir documentos tangenciales en instrucciones ni aplicar cambios sin una guía específica."
  note=f" No se repetirá la acción que ya falló: {', '.join(failed)}." if failed else ""
  return f"Cobertura documental\nLa documentación recuperada no responde directamente al caso de {product}: {symptom}.\n\nOrientación general complementaria\nConfirma el mensaje exacto y el punto en el que ocurre la falla para orientar una búsqueda más precisa. Esta orientación no representa un procedimiento documentado.\n\nRestricciones y validación\nNo realices cambios sensibles sin documentación aplicable.{note}"
