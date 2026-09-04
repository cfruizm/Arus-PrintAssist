from __future__ import annotations
import json,re
RESPONSE_SCHEMA={"type":"object","properties":{"answer":{"type":"string"},"source_usage":{"type":"array","items":{"type":"object"}},"internal_knowledge_used":{"type":"boolean"},"limitations":{"type":"array","items":{"type":"string"}},"next_action":{"type":"string"},"escalation_ready":{"type":"boolean"}},"required":["answer","source_usage","internal_knowledge_used","limitations","next_action","escalation_ready"]}
class Composer:
 def __init__(self,gateway,max_tokens=500):self.gateway=gateway;self.max_tokens=max_tokens
 def compose(self,query,state,plan,candidates):
  from app.llm_gateway.models import LLMRequest
  payload={"query":query,"request_kind":plan.request_kind,"case":state.to_dict(),"sources":candidates,"policy":{"documentation":"Use a source only for claims explicitly supported by its excerpt. Narrow component evidence must not be presented as product-wide coverage.","internal_knowledge":"Allowed when documentation is incomplete. Label it clearly as general complementary guidance. Offer safe options or diagnostic questions. Do not invent product-specific menus, services, logs, parameters or procedures.","continuity":"Do not close the conversation only because documentation is incomplete. Preserve prior attempts and do not repeat unsuccessful actions.","escalation":"If escalation is requested, summarize known facts and ask only for missing operational fields."}}
  system="""Create a natural Spanish support response. First use applicable documentation, then complement with clearly labeled internal knowledge when useful, then state limitations or restrictions. Be helpful and offer next options. Return JSON only. source_usage must list each used source as direct, conditional, context_only or unused with supported_claims. Do not fabricate citations."""
  res=self.gateway.complete(LLMRequest([{"role":"system","content":system},{"role":"user","content":json.dumps(payload,ensure_ascii=False,default=str,separators=(",",":"))}],"agent_core_simplified_answer",self.max_tokens,0.,RESPONSE_SCHEMA))
  if not res.ok or res.finish_reason=="length":return self.fallback(state,plan,candidates,"provider_unavailable")
  try:raw=json.loads(res.text[res.text.find("{"):res.text.rfind("}")+1])
  except Exception:return self.fallback(state,plan,candidates,"invalid_json")
  valid={x["id"] for x in candidates};usage=[]
  for x in raw.get("source_usage") or []:
   if isinstance(x,dict) and x.get("id") in valid and x.get("usage") in {"direct","conditional","context_only","unused"}:usage.append({"id":x["id"],"usage":x["usage"],"supported_claims":[str(c)[:220] for c in x.get("supported_claims") or []]})
  cited=set(re.findall(r"\[(S\d+)\]",str(raw.get("answer") or "")))
  allowed={x["id"] for x in usage if x["usage"] in {"direct","conditional"} and x["supported_claims"]}
  if cited-allowed:return self.fallback(state,plan,candidates,"invalid_citations")
  raw["source_usage"]=usage;raw["mode"]="hybrid";raw["fallback_reason"]=None;return raw
 def fallback(self,state,plan,candidates,reason):
  product=", ".join(getattr(x,"mention","") or getattr(x,"name","") for x in state.active_topic.products) or "el producto indicado"
  if plan.request_kind=="out_of_scope":text="Puedo ayudarte con soporte de impresión, documentación técnica y escalamiento de incidentes. Si tienes un caso de impresión, cuéntame el producto y lo que ocurre."
  elif plan.request_kind=="escalate":text=self.escalation_summary(state)
  elif candidates:text=f"Encontré documentación relacionada con {product}, pero no pude validar con seguridad qué fragmentos responden directamente al caso. Podemos continuar delimitando el síntoma y revisar opciones no invasivas, sin asumir un procedimiento específico."
  else:text=f"No encontré documentación suficiente para resolver el caso de {product}. Como orientación general, podemos precisar el punto de falla, el alcance y el resultado esperado antes de decidir el siguiente paso. No aplicaré cambios específicos sin respaldo."
  return {"answer":text,"source_usage":[{"id":x["id"],"usage":"context_only","supported_claims":[]} for x in candidates],"internal_knowledge_used":True,"limitations":["No se validó un procedimiento específico con la documentación disponible."],"next_action":"Aportar el mensaje exacto o solicitar escalamiento.","escalation_ready":bool(state.case.symptoms),"mode":"safe_fallback","fallback_reason":reason}
 def escalation_summary(self,state):
  products=", ".join(getattr(x,"mention","") or getattr(x,"name","") for x in state.active_topic.products) or "No especificado";symptoms="; ".join(state.case.symptoms) or "No especificado";attempts="; ".join(f"{x.action}: {x.result or 'resultado pendiente'}" for x in state.case.attempts) or "Ninguno informado"
  return f"Preparé el escalamiento con la información disponible:\n\n- Producto: {products}\n- Síntoma: {symptoms}\n- Alcance: {state.case.affected_scope or 'No especificado'}\n- Validaciones realizadas: {attempts}\n\nAntes de finalizar, confirma el contacto, el activo afectado y cualquier mensaje de error disponible."
