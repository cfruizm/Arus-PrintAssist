from __future__ import annotations
import json

class ResponseComposer:
 def __init__(self,gateway=None,max_tokens=420):self.gateway=gateway;self.max_tokens=max(280,min(560,int(max_tokens)))
 def _product(self,state):
  products=getattr(getattr(state,"active_topic",None),"products",[]) or []
  return products[0].canonical_name if products else "el producto consultado"
 def compose_conversation(self,message,decision,state):
  escalation=getattr(state,"escalation",None)
  if decision.intent=="escalation" and escalation and not escalation.pending_field:
   return {"mode":"deterministic_escalation_acknowledgement","text":"El caso quedó preparado para escalamiento con el producto, el síntoma y el alcance registrados. No voy a inventar campos adicionales. Puedes continuar cuando el flujo de escalamiento indique el siguiente dato requerido.","citations":[],"knowledge_used":False}
  if self.gateway is None:return {"mode":"conversation_pending","text":decision.clarification_question or "¿En qué puedo ayudarte?","citations":[],"knowledge_used":False}
  from app.llm_gateway.models import LLMRequest
  payload={"message":message,"conversation_act":decision.conversation_act,"canonical_state":state.to_dict(),"instructions":["Responde en español, natural y brevemente.","No inventes hechos técnicos, emociones, campos de escalamiento ni fuentes.","No repitas preguntas ya respondidas en el estado canónico.","Pregunta únicamente un dato imprescindible realmente ausente."]}
  res=self.gateway.complete(LLMRequest([{"role":"system","content":"Eres la capa conversacional de un agente de soporte. Devuelve solo la respuesta para el usuario."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,default=str)}],"agent_core_v2_conversation_response",240,0.,None))
  if not res.ok or not str(res.text or "").strip() or res.finish_reason=="length":
   reason="provider_error" if not res.ok else "response_truncated" if res.finish_reason=="length" else "empty_response";text=decision.clarification_question or "Necesito un dato adicional para continuar sin asumir información."
   return {"mode":"safe_conversation_fallback","text":text,"citations":[],"knowledge_used":False,"fallback_reason":reason,"provider_result":res.to_dict()}
  return {"mode":"natural_conversation","text":res.text.strip(),"citations":[],"knowledge_used":False,"provider":res.provider,"model":res.model,"usage":res.usage,"finish_reason":res.finish_reason}
 def compose(self,query,decision,state,evidence):
  product=self._product(state);citable=list(evidence.get("citable") or []);unassessed=list(evidence.get("unassessed") or []);case=state.technical_case
  documented=[{"id":item.get("id"),"title":item.get("title"),"url":item.get("url"),"supported_claims":(item.get("semantic_assessment") or {}).get("supported_claims") or [],"conditions":(item.get("semantic_assessment") or {}).get("conditions") or []} for item in citable]
  payload={"current_request":query,"current_intent":decision.intent,"product":product,"case":{"symptoms":list(case.symptoms),"affected_scope":case.affected_scope,"attempts":[{"action":x.action,"result":x.result} for x in case.attempts]},"documented_sources":documented,"unassessed_source_count":len(unassessed),"instructions":["Responde exclusivamente a current_request, no a datos contextuales aislados.","Usa entre 90 y 220 palabras salvo que un procedimiento documentado requiera más.","Si la consulta es conceptual, explica; si es procedural, entrega pasos; si es troubleshooting, propone la siguiente validación.","No conviertas una consulta conceptual en una lista de troubleshooting.","No pidas datos ya presentes en case.","Atribuye a documentación únicamente los supported_claims.","Separa cualquier conocimiento adicional bajo Orientación complementaria.","La orientación complementaria debe ser prudente y no afirmar rutas, servicios, credenciales, compatibilidades o configuraciones específicas no documentadas.","Si la evidencia no responde la solicitud actual, dilo y ofrece una orientación breve, no una respuesta sobre otro tema.","Cierra con una sola pregunta útil solo si hace falta continuar."]}
  if self.gateway is None:return self._safe(product,state,"gateway_not_configured",unassessed)
  from app.llm_gateway.models import LLMRequest
  res=self.gateway.complete(LLMRequest([{"role":"system","content":"Eres un agente de soporte documental. Prioriza la solicitud actual y respeta estrictamente los límites de evidencia. Devuelve solo la respuesta final."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,default=str)}],"agent_core_v2_answer",self.max_tokens,0.,None))
  if not res.ok or not str(res.text or "").strip() or res.finish_reason=="length":
   reason="provider_error" if not res.ok else "response_truncated" if res.finish_reason=="length" else "empty_response";answer=self._safe(product,state,reason,unassessed);answer["provider_result"]=res.to_dict();return answer
  return {"mode":"grounded" if citable else "guarded_internal_knowledge","text":res.text.strip(),"citations":[{"id":item.get("id"),"title":item.get("title"),"url":item.get("url")} for item in citable],"knowledge_used":not bool(citable) or "Orientación complementaria" in res.text,"unassessed_sources":[item.get("id") for item in unassessed],"provider":res.provider,"model":res.model,"usage":res.usage,"finish_reason":res.finish_reason}
 def _safe(self,product,state,reason,unassessed):
  scope=state.technical_case.affected_scope;context=f" y considerando el alcance registrado ({scope})" if scope else ""
  text=f"No pude confirmar en la documentación recuperada una respuesta específica para la solicitud actual sobre {product}. **Orientación complementaria:** puedo continuar con una revisión segura y gradual{context}, o preparar el escalamiento sin inventar un procedimiento. Indica el resultado concreto que buscas obtener o el mensaje observado para enfocar la siguiente validación."
  return {"mode":"safe_hybrid_fallback","text":text,"citations":[],"knowledge_used":True,"unassessed_sources":[item.get("id") for item in unassessed],"fallback_reason":reason}
