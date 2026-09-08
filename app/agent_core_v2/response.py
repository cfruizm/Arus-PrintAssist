from __future__ import annotations
import json,re

class ResponseComposer:
 def __init__(self,gateway=None,max_tokens=420):self.gateway=gateway;self.max_tokens=max_tokens
 def compose_conversation(self,message,decision,state):
  if decision.action=="decline_out_of_scope":return {"mode":"out_of_scope","text":"Puedo ayudarte con soporte de impresión, sus plataformas, dispositivos, suministros y procesos. Esa consulta está fuera de este alcance. Si tienes una situación relacionada con impresión, cuéntame y la revisamos.","citations":[],"knowledge_used":False,"scope":"printing"}
  if self.gateway is None:return {"mode":"conversation_pending","text":decision.clarification_question or "¿En qué puedo ayudarte?","citations":[],"knowledge_used":False}
  from app.llm_gateway.models import LLMRequest
  payload={"message":message,"conversation_act":decision.conversation_act,"canonical_state":state.to_dict(),"policy":["Respond naturally and briefly in Spanish.","This is a lateral or workflow response; do not cite documents.","Do not alter or invent technical facts.","For capability, explain documentation-first support, clearly labeled internal knowledge, safe options, case memory and escalation assistance.","For social or farewell, respond in context rather than using a universal greeting.","For escalation, use only the actual canonical escalation status, pending_field and collected_fields. Ask only the real pending field when present; do not invent a parallel escalation schema.","For clarification, use the active product and case to ask one precise question."]}
  res=self.gateway.complete(LLMRequest([{"role":"system","content":"You are the conversational layer of a printing support agent. Produce only the user-facing response."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,default=str)}],"agent_core_v2_conversation_response",min(self.max_tokens,220),0.,None))
  if not res.ok or res.finish_reason=="length":
   text=decision.clarification_question or ("La solicitud de escalamiento quedó registrada. Continuemos con el dato pendiente que muestre el caso." if decision.intent=="escalation" else "Entendido. Podemos continuar con el caso cuando quieras.")
   return {"mode":"safe_conversation_fallback","text":text,"citations":[],"knowledge_used":False,"fallback_reason":self._failure_reason(res)}
  return {"mode":"natural_conversation","text":res.text.strip(),"citations":[],"knowledge_used":False,"provider":res.provider,"model":res.model,"usage":res.usage,"finish_reason":res.finish_reason}
 def compose(self,message,decision,state,evidence):
  approved=(evidence.get("direct") or [])+(evidence.get("partial") or [])+(evidence.get("conditional") or [])
  contextual=evidence.get("contextual") or [];unassessed=evidence.get("unassessed") or []
  if self.gateway is None:return {"mode":"pending","text":"Respuesta pendiente.","citations":[],"knowledge_used":False}
  from app.llm_gateway.models import LLMRequest
  sources=[];seen=set()
  applicability_rank={"direct":0,"conditional":1,"partial":2,"contextual":3}
  def evidence_rank(item):
   assessment=item.get("semantic_assessment") or {}
   applicability=str(assessment.get("applicability") or "partial").lower()
   subject=0 if assessment.get("subject_match")=="same" else 1
   task=0 if assessment.get("task_match")=="same" else 1
   claims=assessment.get("supported_claims") or []
   relevance=-float(item.get("query_relevance_score") or item.get("retrieval_score") or 0)
   return (applicability_rank.get(applicability,9),subject,task,0 if claims else 1,relevance)
  for item in sorted(approved,key=evidence_rank):
   identity=str(item.get("url") or item.get("source_url") or item.get("title") or item.get("id"));a=item.get("semantic_assessment") or {}
   claims=[str(x).strip() for x in (a.get("supported_claims") or []) if str(x).strip()]
   if identity in seen or not claims:continue
   seen.add(identity);sources.append({"id":item.get("id"),"title":item.get("title") or "Fuente documental","applicability":a.get("applicability"),"scope_relation":a.get("scope_relation"),"source_object":a.get("source_object"),"supported_claims":claims[:5],"conditions":(a.get("conditions") or [])[:3]})
   if len(sources)>=3:break
  background=[{"id":x.get("id"),"title":x.get("title") or "Fuente relacionada","excerpt":x.get("text","")[:500],"status":"contextual" if x in contextual else "unassessed"} for x in (contextual+unassessed)[:1]]
  if not sources and decision.intent in {"procedural","troubleshooting","requirements"}:
   return self._unsupported_action_response(decision,state,background,"no_approved_evidence")
  payload={"request":message,"current_intent":decision.intent,"case":state.to_dict(),"documented_sources":sources,"related_unverified_sources":background,"policy":["Answer in Spanish and be concise.","Documentation is primary. Cite only supported_claims from documented_sources using [S#].","If evidence is narrower than the request, label its scope accurately; do not claim that documentation is absent when documented_sources is not empty.","If useful, add a short clearly labeled section 'Orientación general complementaria'.","State relevant restrictions and do not invent product-specific menus, logs, services, parameters or procedures.","Answer the current request and do not repeat an earlier fallback."]}
  res=self.gateway.complete(LLMRequest([{"role":"system","content":"Act as a natural printing support assistant. Use the compact approved evidence. Separate documented evidence from optional complementary knowledge."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,default=str)}],"agent_core_v2_answer",min(self.max_tokens,650),0.,None))
  if not res.ok or res.finish_reason=="length":return self._evidence_recovery(decision,state,sources,background,self._failure_reason(res))
  text=res.text.strip();used=set(re.findall(r"\[(S\d+)\]",text));valid={x["id"] for x in sources if x.get("id")}
  if not text:return self._evidence_recovery(decision,state,sources,background,"answer_empty")
  if used-valid:return self._evidence_recovery(decision,state,sources,background,"invalid_citations")
  knowledge_used="orientación general complementaria" in text.casefold()
  return {"mode":"documented" if sources and not knowledge_used else "hybrid_supported","text":text,"citations":sorted(used),"knowledge_used":knowledge_used,"unassessed_sources":[x["title"] for x in background if x["status"]=="unassessed"],"provider":res.provider,"model":res.model,"usage":res.usage,"finish_reason":res.finish_reason,"evidence_selection":{"original_approved_count":len(approved),"selected_count":len(sources),"selected_ids":[x["id"] for x in sources if x.get("id")]}}
 def _unsupported_action_response(self,decision,state,background,reason):
  product=self._product_name(state)
  if decision.intent=="procedural":
   text=(f"No encontré evidencia aprobada para indicar los pasos exactos en {product}. "
         "Para evitar inventar rutas, menús o cambios, necesito una fuente documental más específica. "
         "Puedo seguir buscando si indicas el módulo, versión o entorno, o ayudarte a preparar el caso para escalamiento.")
  elif decision.intent=="troubleshooting":
   text=(f"No encontré evidencia aprobada para recomendar acciones técnicas específicas en {product}. "
         "Comparte el síntoma exacto, el alcance de la afectación y las validaciones ya realizadas para orientar una búsqueda más precisa o preparar el escalamiento.")
  else:
   text=(f"No encontré evidencia aprobada suficiente para confirmar los requisitos de {product}. "
         "No presentaré valores, compatibilidades ni prerrequisitos sin respaldo documental.")
  return {"mode":"evidence_insufficient","text":text,"citations":[],"knowledge_used":False,"unassessed_sources":[x["title"] for x in background],"fallback_reason":reason,"evidence_selection":{"original_approved_count":0,"selected_count":0,"selected_ids":[]}}
 def _product_name(self,state):
  names=[]
  for x in state.active_topic.products:
   raw=str(getattr(x,"canonical_name","") or getattr(x,"matched_text","") or "");mention=str(getattr(x,"matched_text","") or "");names.append(mention if "_" in raw and mention else raw.replace("_"," ").title())
  return ", ".join(names) or "el producto indicado"
 def _failure_reason(self,res):
  if getattr(res,"finish_reason",None)=="length":return "answer_truncated"
  error=str(getattr(res,"error_message","") or getattr(res,"error","") or "").casefold()
  if any(x in error for x in ("límite de tokens de la sesión","session token","token budget")):return "session_token_budget_exhausted"
  if any(x in error for x in ("429","rate limit","too many requests")):return "provider_rate_limited"
  if not getattr(res,"ok",False):return "provider_unavailable"
  return "answer_generation_failed"
 def _evidence_recovery(self,decision,state,sources,background,reason):
  if not sources:return self._fallback(decision,state,background,reason)
  claims=[];conditions=[];citations=[]
  for source in sources:
   sid=source.get("id")
   if sid:citations.append(sid)
   for claim in source.get("supported_claims") or []:
    claim=" ".join(str(claim).split())
    if claim and claim.casefold() not in {x.casefold() for x in claims}:claims.append(claim)
   for condition in source.get("conditions") or []:
    condition=" ".join(str(condition).split())
    if condition and condition.casefold() not in {x.casefold() for x in conditions}:conditions.append(condition)
  lines=["### Información documentada",""]+[f"- {claim} [{citations[min(i,len(citations)-1)]}]" if citations else f"- {claim}" for i,claim in enumerate(claims[:6])]
  if conditions:lines += ["","### Alcance y condiciones",""]+[f"- {x}" for x in conditions[:4]]
  lines += ["","### Fuentes",""]+[f"- [{x.get('id')}] {x.get('title')}" for x in sources]
  return {"mode":"evidence_backed_recovery","text":"\n".join(lines),"citations":sorted(set(citations)),"knowledge_used":False,"unassessed_sources":[x["title"] for x in background if x["status"]=="unassessed"],"fallback_reason":reason,"evidence_selection":{"selected_count":len(sources),"selected_ids":citations}}
 def _fallback(self,decision,state,background,reason):
  product=self._product_name(state)
  if decision.intent=="troubleshooting":text=f"No pude validar un procedimiento específico para {product}. **Orientación general complementaria:** confirma el mensaje exacto, el alcance del impacto y si el fallo ocurre siempre o bajo una condición concreta. Estas validaciones son generales y no sustituyen documentación del producto. Con esos datos puedo proponerte opciones seguras o preparar el escalamiento."
  elif decision.intent=="procedural":text=f"No pude confirmar los pasos exactos para {product}. **Orientación general complementaria:** precisemos qué operación deseas realizar, sobre qué componente y en qué entorno. No recomendaré rutas o cambios específicos sin respaldo documental."
  elif decision.intent=="conceptual":text=f"No hay afirmaciones documentales aprobadas suficientes para describir {product}. Puedo ofrecer una explicación general claramente identificada como conocimiento complementario o realizar una búsqueda documental más específica."
  else:text=f"La documentación disponible no permitió responder completamente sobre {product}. **Orientación general complementaria:** puedo ayudarte a delimitar el alcance, comparar opciones seguras y recopilar la información necesaria antes de escalar."
  return {"mode":"safe_hybrid_fallback","text":text,"citations":[],"knowledge_used":True,"unassessed_sources":[x["title"] for x in background],"fallback_reason":reason}
