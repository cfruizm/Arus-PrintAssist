from __future__ import annotations
import json

class ResponseComposer:
 def __init__(self,gateway=None,max_tokens=420):self.gateway=gateway;self.max_tokens=max(260,min(700,int(max_tokens)))
 def _product(self,state):
  products=getattr(getattr(state,"active_topic",None),"products",[]) or []
  return products[0].canonical_name if products else "el producto consultado"
 def compose_conversation(self,message,decision,state):
  if self.gateway is None:return {"mode":"conversation_pending","text":decision.clarification_question or "¿En qué puedo ayudarte?","citations":[],"knowledge_used":False}
  from app.llm_gateway.models import LLMRequest
  payload={"message":message,"conversation_act":decision.conversation_act,"canonical_state":state.to_dict(),"instructions":["Responde en español, natural y brevemente.","No inventes hechos técnicos ni fuentes.","No repitas datos que ya estén en el estado canónico.","Para aclarar, pregunta solo el dato mínimo realmente ausente.","Para escalamiento, usa únicamente el estado canónico existente."]}
  res=self.gateway.complete(LLMRequest([{"role":"system","content":"Eres la capa conversacional de un agente de soporte de impresión. Devuelve solo la respuesta para el usuario."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,default=str)}],"agent_core_v2_conversation_response",min(self.max_tokens,260),0.,None))
  if not res.ok or not str(res.text or "").strip() or res.finish_reason=="length":
   reason="provider_error" if not res.ok else "response_truncated" if res.finish_reason=="length" else "empty_response"
   text=decision.clarification_question or ("La solicitud de escalamiento quedó registrada. Continuemos con el dato pendiente del caso." if decision.intent=="escalation" else "Entendido. Podemos continuar con el caso cuando quieras.")
   return {"mode":"safe_conversation_fallback","text":text,"citations":[],"knowledge_used":False,"fallback_reason":reason,"provider_result":res.to_dict()}
  return {"mode":"natural_conversation","text":res.text.strip(),"citations":[],"knowledge_used":False,"provider":res.provider,"model":res.model,"usage":res.usage,"finish_reason":res.finish_reason}
 def compose(self,query,decision,state,evidence):
  product=self._product(state);citable=list(evidence.get("citable") or []);unassessed=list(evidence.get("unassessed") or []);case=state.technical_case
  documented=[{"id":item.get("id"),"title":item.get("title"),"url":item.get("url"),"supported_claims":(item.get("semantic_assessment") or {}).get("supported_claims") or [],"conditions":(item.get("semantic_assessment") or {}).get("conditions") or []} for item in citable]
  payload={"request":query,"product":product,"case":{"symptoms":list(case.symptoms),"affected_scope":case.affected_scope,"attempts":[{"action":x.action,"result":x.result} for x in case.attempts]},"documented_sources":documented,"unassessed_source_count":len(unassessed),"instructions":["Responde en español y comienza con ayuda accionable.","No pidas información que ya figure en case.","Distingue explícitamente Evidencia documentada de Orientación complementaria.","Solo atribuye a documentación los supported_claims recibidos.","Si no hay supported_claims, dilo en una frase y ofrece entre 3 y 5 validaciones generales, seguras y reversibles.","No inventes rutas, comandos, credenciales, puertos, nombres de servicios ni procedimientos específicos.","Cierra con una sola pregunta útil para continuar o con la opción de escalar.","Mantén la respuesta completa por debajo de 330 palabras."]}
  if self.gateway is None:return self._safe_hybrid(product,state,"gateway_not_configured",unassessed)
  from app.llm_gateway.models import LLMRequest
  res=self.gateway.complete(LLMRequest([{"role":"system","content":"Eres un agente de soporte documental. Sigue estrictamente la separación entre evidencia y orientación complementaria. Devuelve solo la respuesta final."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,default=str)}],"agent_core_v2_answer",self.max_tokens,0.,None))
  if not res.ok or not str(res.text or "").strip() or res.finish_reason=="length":
   reason="provider_error" if not res.ok else "response_truncated" if res.finish_reason=="length" else "empty_response"
   answer=self._safe_hybrid(product,state,reason,unassessed);answer["provider_result"]=res.to_dict();return answer
  return {"mode":"grounded" if citable else "guarded_internal_knowledge","text":res.text.strip(),"citations":[{"id":item.get("id"),"title":item.get("title"),"url":item.get("url")} for item in citable],"knowledge_used":not bool(citable) or "Orientación complementaria" in res.text,"unassessed_sources":[item.get("id") for item in unassessed],"provider":res.provider,"model":res.model,"usage":res.usage,"finish_reason":res.finish_reason}
 def _safe_hybrid(self,product,state,reason,unassessed):
  case=state.technical_case;known=[]
  if case.symptoms:known.append("el síntoma registrado")
  if case.affected_scope:known.append(f"el alcance indicado ({case.affected_scope})")
  context=" y ".join(known) if known else "la información compartida"
  text=f"No pude confirmar un procedimiento específico documentado para {product}. **Orientación complementaria:** con {context}, conviene revisar primero condiciones compartidas, cambios recientes, conectividad general y registros disponibles, sin aplicar cambios irreversibles. Si compartes el mensaje exacto o el último cambio observado, puedo acotar la siguiente validación o preparar el escalamiento."
  return {"mode":"safe_hybrid_fallback","text":text,"citations":[],"knowledge_used":True,"unassessed_sources":[item.get("id") for item in unassessed],"fallback_reason":reason}
