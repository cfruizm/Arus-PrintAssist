from __future__ import annotations
import json,re
class ResponseComposer:
 def __init__(self,gateway=None,max_tokens=700):self.gateway=gateway;self.max_tokens=max(320,min(720,int(max_tokens)))
 def compose_conversation(self,message,decision,state):
  if self.gateway is None:return {"mode":"conversation_pending","text":decision.clarification_question or "¿En qué puedo ayudarte?","citations":[],"knowledge_used":False}
  from app.llm_gateway.models import LLMRequest
  payload={"message":message,"conversation_act":decision.conversation_act,"canonical_state":state.to_dict(),"policy":["Respond naturally and briefly in Spanish.","This is a lateral or workflow response; do not cite documents.","Do not alter or invent technical facts.","For capability, explain documentation-first support, clearly labeled internal knowledge, safe options, case memory and escalation assistance.","For social or farewell, respond in context rather than using a universal greeting.","For escalation, use only the actual canonical escalation status, pending_field and collected_fields. Ask only the real pending field when present; do not invent a parallel escalation schema.","For clarification, use the active product and case to ask one precise question."]}
  res=self.gateway.complete(LLMRequest([{"role":"system","content":"You are the conversational layer of a printing support agent. Produce only the user-facing response."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,default=str)}],"agent_core_v2_conversation_response",min(self.max_tokens,220),0.,None))
  if not res.ok or res.finish_reason=="length":
   text=decision.clarification_question or ("La solicitud de escalamiento quedó registrada. Continuemos con el dato pendiente que muestre el caso." if decision.intent=="escalation" else "Entendido. Podemos continuar con el caso cuando quieras.")
   return {"mode":"safe_conversation_fallback","text":text,"citations":[],"knowledge_used":False}
  return {"mode":"natural_conversation","text":res.text.strip(),"citations":[],"knowledge_used":False,"provider":res.provider,"model":res.model,"usage":res.usage,"finish_reason":res.finish_reason}
 def _answer_budget(self,message,evidence):
  text=str(message or ""); completeness=dict((evidence or {}).get("answer_completeness") or {})
  broad=bool(completeness.get("broad_request")) or len((evidence or {}).get("citable") or [])>=3
  requested=680 if broad else 460
  return min(self.max_tokens,requested)
 def _clean_truncation(self,text):
  value=str(text or "").strip()
  if not value:return value
  # Never expose an unfinished sentence, list marker, heading or open markdown token.
  cuts=[value.rfind(mark) for mark in (". ",".\n","! ","!\n","? ","?\n")];cut=max(cuts)
  if cut>=max(80,int(len(value)*.55)):value=value[:cut+1].rstrip()
  value=re.sub(r"\n(?:#{1,6}\s+[^\n]*|(?:[-*]|\d+[.)])\s*)$","",value).rstrip()
  if value.count("**")%2:value=value.rsplit("**",1)[0].rstrip()
  return value
 def compose(self,message,decision,state,evidence):
  approved=(evidence.get("direct") or [])+(evidence.get("partial") or [])+(evidence.get("conditional") or []);contextual=evidence.get("contextual") or [];unassessed=evidence.get("unassessed") or []
  if self.gateway is None:return {"mode":"pending","text":"Respuesta pendiente.","citations":[],"knowledge_used":False}
  from app.llm_gateway.models import LLMRequest
  sources=[]
  for item in approved[:3]:
   a=item.get("semantic_assessment") or {};sources.append({"id":item["id"],"title":item["title"],"scope_relation":a.get("scope_relation"),"source_object":a.get("source_object"),"supported_claims":a.get("supported_claims") or [],"conditions":a.get("conditions") or []})
  background=[{"id":x["id"],"title":x["title"],"excerpt":x.get("text","")[:900],"status":"contextual" if x in contextual else "unassessed"} for x in (contextual+unassessed)[:3]]
  payload={"request":message,"current_intent":decision.intent,"case":state.to_dict(),"documented_sources":sources,"related_unverified_sources":background,"policy":["Documentation is primary. Cite only supported_claims from documented_sources.","If evidence is narrower than the request, label it as partial and never present it as complete product coverage.","If documentation is incomplete, add a clearly labeled section 'Orientación general complementaria' using internal model knowledge.","Complementary guidance must provide useful safe options or diagnostic questions, not empty promises.","State restrictions and avoid inventing product-specific menus, logs, services, parameters or procedures.","Do not close the conversation merely because documentation is incomplete.","Do not repeat unsuccessful actions stored in the case.","Answer the current request, never the historical intent.","Use no more than five compact sections. Put the requested scope first and finish every sentence."] ,"response_contract":{"complete_over_comprehensive":True,"maximum_sections":5,"concise":True}}
  res=self.gateway.complete(LLMRequest([{"role":"system","content":"Act as a natural printing support assistant. Separate documented evidence, complementary internal knowledge, and restrictions."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,default=str)}],"agent_core_v2_answer",self._answer_budget(message,evidence),0.,None))
  if not res.ok:return self._fallback(decision,state,background,"provider_unavailable")
  if res.finish_reason=="length":
   clean=self._clean_truncation(res.text)
   return {"mode":"bounded_grounded_answer","text":clean+"\n\nLa respuesta fue cerrada en el último punto completo por el límite temporal de salida del proveedor.","citations":citations,"knowledge_used":False,"provider":res.provider,"model":res.model,"usage":res.usage,"finish_reason":res.finish_reason,"truncation_handled":True}
  text=res.text.strip();used=set(re.findall(r"\[(S\d+)\]",text));valid={x["id"] for x in sources}
  if used-valid:return self._fallback(decision,state,background,"invalid_citations")
  knowledge_used="orientación general complementaria" in text.casefold()
  return {"mode":"documented" if sources and not knowledge_used else "hybrid_supported","text":text,"citations":sorted(used),"knowledge_used":knowledge_used,"unassessed_sources":[x["title"] for x in background if x["status"]=="unassessed"],"provider":res.provider,"model":res.model,"usage":res.usage,"finish_reason":res.finish_reason}
 def _fallback(self,decision,state,background,reason):
  names=[]
  for x in state.active_topic.products:
   raw=str(getattr(x,"canonical_name","") or getattr(x,"matched_text","") or "");mention=str(getattr(x,"matched_text","") or "");names.append(mention if "_" in raw and mention else raw.replace("_"," ").title())
  product=", ".join(names) or "el producto indicado"
  if decision.intent=="troubleshooting":text=f"No pude validar un procedimiento específico para {product}. **Orientación general complementaria:** confirma el mensaje exacto, el alcance del impacto y si el fallo ocurre siempre o bajo una condición concreta. Estas validaciones son generales y no sustituyen documentación del producto. Con esos datos puedo proponerte opciones seguras o preparar el escalamiento."
  elif decision.intent=="procedural":text=f"No pude confirmar los pasos exactos para {product}. **Orientación general complementaria:** precisemos qué operación deseas realizar, sobre qué componente y en qué entorno. No recomendaré rutas o cambios específicos sin respaldo documental."
  elif decision.intent=="conceptual":text=f"No pude validar una descripción documental completa de {product}. Puedo ofrecer una explicación general claramente identificada como conocimiento complementario o seguir buscando una fuente de introducción del producto."
  else:text=f"La documentación disponible no permitió responder completamente sobre {product}. **Orientación general complementaria:** puedo ayudarte a delimitar el alcance, comparar opciones seguras y recopilar la información necesaria antes de escalar."
  return {"mode":"safe_hybrid_fallback","text":text,"citations":[],"knowledge_used":True,"unassessed_sources":[x["title"] for x in background],"fallback_reason":reason}
