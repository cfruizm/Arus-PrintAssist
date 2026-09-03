from __future__ import annotations
import json,re
class ResponseComposer:
 def __init__(self,gateway=None,max_tokens=400):self.gateway=gateway;self.max_tokens=max_tokens
 def compose(self,message,decision,state,evidence):
  docs=[{"id":x["id"],"title":x["title"],"url":x["url"],"text":x["text"][:2200]} for x in (evidence.get("citable") or [])[:3]]
  if decision.action=="ask_clarification":return {"mode":"clarification","text":decision.clarification_question or "Necesito una precisión adicional para continuar.","citations":[],"knowledge_used":False}
  if decision.action!="retrieve":return {"mode":"directive","text":"","citations":[],"knowledge_used":False}
  if self.gateway is None:return {"mode":"documented_pending" if docs else "hybrid_pending","text":"Respuesta pendiente del compositor LLM.","citations":[x["id"] for x in docs],"knowledge_used":not bool(docs)}
  from app.llm_gateway.models import LLMRequest
  products=[x.canonical_name for x in state.active_topic.products];symptoms=list(state.technical_case.symptoms);attempts=[{"action":x.action,"result":x.result} for x in state.technical_case.attempts];mode="documented" if docs else "hybrid_general"
  rules=["Máximo 180 palabras.","Separa Cobertura documental, Orientación general complementaria y Restricciones y validación cuando uses conocimiento general.","No inventes procedimientos, rutas de menú, servicios, logs, parámetros ni funciones del producto.","Para una intención procedural sin fuentes directas, no propongas pasos hipotéticos ni cómo suele hacerse en otros productos; pide confirmar la función exacta o la opción visible.","Las citas solo respaldan texto de sources.","No listes como fuente documentos no citables.","No menciones acciones fallidas inexistentes."]
  prompt={"message":message,"intent":decision.intent,"products":products,"symptoms":symptoms,"attempts":attempts,"sources":docs,"mode":mode,"rules":rules}
  r=self.gateway.complete(LLMRequest([{"role":"system","content":"Compón una respuesta segura de soporte. El conocimiento general nunca es documentación."},{"role":"user","content":json.dumps(prompt,ensure_ascii=False,default=str)}],"agent_core_v2_answer",self.max_tokens,0.,None))
  if not r.ok or r.finish_reason=="length":return {"mode":"truncated_fallback" if r.finish_reason=="length" else "provider_error","text":self._fallback(decision.intent,products,symptoms,attempts),"citations":[],"knowledge_used":False,"finish_reason":r.finish_reason}
  text=r.text.strip();used=set(re.findall(r"\[(S\d+)\]",text));valid={x["id"] for x in docs}
  if used-valid or (docs and not used):return {"mode":"invalid_citations","text":self._fallback(decision.intent,products,symptoms,attempts),"citations":[],"knowledge_used":False}
  return {"mode":mode,"text":text,"citations":sorted(used),"knowledge_used":not bool(docs) or "Orientación general complementaria" in text,"provider":r.provider,"model":r.model,"usage":r.usage,"finish_reason":r.finish_reason}
 def _fallback(self,intent,products,symptoms,attempts):
  product=", ".join(products) or "el producto indicado"
  if intent=="procedural":return f"Cobertura documental\nNo se encontraron pasos directamente aplicables para el procedimiento en {product}.\n\nOrientación general complementaria\nNo es seguro inferir que la función exista ni proponer una ruta de configuración. Confirma el nombre exacto de la opción visible o la modalidad que intentas configurar.\n\nRestricciones y validación\nNo conviertas documentos tangenciales en instrucciones ni apliques cambios sin una guía específica."
  symptom="; ".join(symptoms) or "el síntoma informado";failed=[x["action"] for x in attempts if x.get("result")=="failed"];note=f" No se repetirá la acción fallida: {', '.join(failed)}." if failed else ""
  return f"Cobertura documental\nLa documentación recuperada no responde directamente al caso de {product}: {symptom}.\n\nOrientación general complementaria\nConfirma el mensaje exacto y el punto donde ocurre la falla. Esta orientación no representa un procedimiento documentado.\n\nRestricciones y validación\nNo realices cambios sensibles sin documentación aplicable.{note}"
