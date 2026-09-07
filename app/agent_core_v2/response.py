from __future__ import annotations
import json,re
class ResponseComposer:
 def __init__(self,gateway=None,max_tokens=400):self.gateway=gateway;self.max_tokens=max_tokens
 def compose(self,message,decision,state,evidence):
  approved=(evidence.get("direct") or [])+(evidence.get("partial") or [])+(evidence.get("conditional") or []);contextual=evidence.get("contextual") or [];unassessed=evidence.get("unassessed") or []
  if self.gateway is None:return {"mode":"pending","text":"Respuesta pendiente.","citations":[],"knowledge_used":False}
  from app.llm_gateway.models import LLMRequest
  sources=[]
  for item in approved[:3]:
   a=item.get("semantic_assessment") or {};sources.append({"id":item["id"],"title":item["title"],"excerpt":item.get("text","")[:1600],"usage":"approved","supported_claims":a.get("supported_claims") or [],"conditions":a.get("conditions") or []})
  background=[]
  for item in (contextual+unassessed)[:3]:background.append({"id":item["id"],"title":item["title"],"excerpt":item.get("text","")[:900],"status":"contextual" if item in contextual else "unassessed"})
  payload={"request":message,"current_intent":decision.intent,"case_state":state.to_dict(),"approved_sources":sources,"background_candidates":background,"policy":["Use approved_sources only for cited claims.","An unassessed candidate was not rejected; mention only that related documentation was found and applicability could not be confirmed.","When documentation is insufficient, provide useful general complementary guidance, clearly labeled and with restrictions.","Do not invent product-specific procedures, menus, services, logs or parameters.","Do not close the conversation merely because documentation is incomplete.","Answer the current request, not the historical intent.","Never expose internal field names or English intent IDs."]}
  res=self.gateway.complete(LLMRequest([{"role":"system","content":"Respond naturally in Spanish as a printing support assistant. Separate documented information, complementary model knowledge, and limitations."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,default=str)}],"agent_core_v2_answer",self.max_tokens,0.,None))
  if not res.ok or res.finish_reason=="length":return self._fallback(decision,state,background,"provider_unavailable")
  text=res.text.strip();used=set(re.findall(r"\[(S\d+)\]",text));valid={x["id"] for x in sources}
  if used-valid:return self._fallback(decision,state,background,"invalid_citations")
  return {"mode":"hybrid","text":text,"citations":sorted(used),"knowledge_used":not bool(sources) or "complementaria" in text.casefold(),"limitations_present":any(word in text.casefold() for word in ["limitación","restricción","no está documentado","no se encontró"]),"unassessed_sources":[x["title"] for x in background if x["status"]=="unassessed"],"provider":res.provider,"model":res.model,"usage":res.usage,"finish_reason":res.finish_reason}
 def _fallback(self,decision,state,background,reason):
  names=[]
  for x in state.active_topic.products:
   n=str(getattr(x,"canonical_name","") or getattr(x,"matched_text","") or "");m=str(getattr(x,"matched_text","") or "");names.append(m if "_" in n and m else n.replace("_"," ").title())
  product=", ".join(names) or "el producto indicado"
  if decision.intent=="conceptual":body=f"Puedo explicarte el propósito general de {product}, pero en este momento no pude validar una fuente suficientemente específica. Como orientación complementaria, puedo resumir su función general y después revisar requisitos, arquitectura o soporte según lo que necesites."
  elif decision.intent=="procedural":body=f"No pude confirmar un procedimiento documentado para {product}. Puedo ayudarte a precisar la operación y proponer validaciones seguras, sin inventar rutas o funciones del producto."
  else:body=f"La documentación disponible no permitió confirmar una respuesta completa para {product}. Podemos continuar con orientación general, opciones no invasivas y recopilación de evidencia antes de escalar."
  return {"mode":"safe_fallback","text":body,"citations":[],"knowledge_used":True,"limitations_present":True,"unassessed_sources":[x["title"] for x in background],"fallback_reason":reason}
