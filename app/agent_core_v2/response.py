from __future__ import annotations
import json,re
def __init__(self,gateway=None,max_tokens=420):self.gateway=gateway;self.max_tokens=max(320,min(720,int(max_tokens)))
 def compose_conversation(self,message,decision,state):
  if decision.action in {"start_escalation","continue_escalation","resume_escalation"}:
   from .escalation_flow import NativeEscalationCoordinator
   coordinator=NativeEscalationCoordinator()
   if state.escalation.status=="ready": text=coordinator.summary(state)
   else: text=coordinator.question_for(state.escalation.pending_field) or "Continuemos con la información pendiente del escalamiento."
   return {"mode":"native_escalation","text":text,"citations":[],"knowledge_used":False,"escalation_status":state.escalation.status,"pending_field":state.escalation.pending_field}
  if decision.action=="decline_out_of_scope":return {"mode":"out_of_scope","text":"Puedo ayudarte con soporte de impresión, sus plataformas, dispositivos, suministros y procesos. Esa consulta está fuera de este alcance. Si tienes una situación relacionada con impresión, cuéntame y la revisamos.","citations":[],"knowledge_used":False,"scope":"printing"}
  if self.gateway is None:return {"mode":"conversation_pending","text":decision.clarification_question or "¿En qué puedo ayudarte?","citations":[],"knowledge_used":False}
  from app.llm_gateway.models import LLMRequest
  payload={"message":message,"conversation_act":decision.conversation_act,"canonical_state":state.to_dict(),"state":state.to_dict(),"policy":["Respond naturally and briefly in Spanish when the user is speaking Spanish; otherwise answer in their language.","Use only the actual canonical escalation status, pending_field and collected_fields.","Ask only the real pending field when present; do not invent a parallel escalation schema.","Be concise and do not cite documents for lateral or workflow replies.","Do not alter or invent technical facts.","For capability, explain documentation-first support and label internal knowledge clearly.","For social or farewell responses, respond in context rather than using a universal greeting."]}
  res=self.gateway.complete(LLMRequest([{"role":"system","content":"You are the conversational layer of a printing support agent. Produce only the user-facing response."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,default=str)}],"agent_core_v2_conversation_response",min(self.max_tokens,220),0.,None))
  if not res.ok or res.finish_reason=="length":
   text=decision.clarification_question or ("La solicitud de escalamiento quedó registrada. Continuemos con el dato pendiente que muestre el caso." if decision.intent=="escalation" else "Entendido. Podemos continuar con el caso cuando quieras.")
   return {"mode":"safe_conversation_fallback","text":text,"citations":[],"knowledge_used":False,"fallback_reason":self._failure_reason(res)}
  return {"mode":"natural_conversation","text":res.text.strip(),"citations":[],"knowledge_used":False,"provider":res.provider,"model":res.model,"usage":res.usage,"finish_reason":res.finish_reason}
 def _citation(self,item):
  m=item.get("metadata") or {}
  return {"id":item.get("id"),"title":item.get("title"),"url":item.get("url"),"page":str(m.get("page_label") or m.get("page") or "")}
 def _budget(self,evidence):return min(self.max_tokens,680 if (evidence.get("answer_completeness") or {}).get("broad_request") else 460)
 def _clean(self,text):
  value=str(text or "").strip();positions=[value.rfind(x) for x in (". ",".\n","! ","!\n","? ","?\n")];cut=max(positions) if positions else -1
  if cut>=max(80,int(len(value)*.55)):value=value[:cut+1].rstrip()
  if value.count("**")%2:value=value.rsplit("**",1)[0].rstrip()
  return value
 def compose(self,message,decision,state,evidence):
  approved=(evidence.get("direct") or [])+(evidence.get("partial") or [])+(evidence.get("conditional") or [])
  contextual=evidence.get("contextual") or [];unassessed=evidence.get("unassessed") or []
  citations=[];seen=set()
  for item in approved:
   key=(item.get("url"),str((item.get("metadata") or {}).get("page_label") or (item.get("metadata") or {}).get("page")))
   if key not in seen:seen.add(key);citations.append(self._citation(item))
  if self.gateway is None:return {"mode":"pending","text":"Respuesta pendiente.","citations":citations,"knowledge_used":False}
  from app.llm_gateway.models import LLMRequest
  sources=[];seen=set()
  applicability_rank={"direct":0,"conditional":1,"partial":2,"contextual":3}
  def _claim_quality(claim):
   value=" ".join(str(claim or "").split())
   if not value:return -20
   score=min(len(value),500)/100
   if value.count("...")>=2:score-=15
   if len(re.findall(r"\.{4,}\s*\d+",value))>=2:score-=15
   if len(re.findall(r"(?:^|\s)\d{1,3}(?:\s|$)",value))>=8:score-=8
   return score
  def evidence_rank(item):
   assessment=item.get("semantic_assessment") or {}
   applicability=str(assessment.get("applicability") or "partial").lower()
   subject=0 if assessment.get("subject_match")=="same" else 1
   task=0 if assessment.get("task_match")=="same" else (1 if assessment.get("task_match")=="related" else 2)
   claims=assessment.get("supported_claims") or []
   claim_quality=max([_claim_quality(x) for x in claims] or [-20])
   relevance=-float(item.get("query_relevance_score") or item.get("retrieval_score") or 0)
   return (subject,task,applicability_rank.get(applicability,9),-claim_quality,relevance)
  for item in sorted(approved,key=evidence_rank):
   identity=str(item.get("url") or item.get("source_url") or item.get("title") or item.get("id"));a=item.get("semantic_assessment") or {}
   claims=[str(x).strip() for x in (a.get("supported_claims") or []) if str(x).strip() and _claim_quality(x)>-5]
   if identity in seen or not claims:continue
   if a.get("subject_match") not in (None,"same"):continue
   seen.add(identity);sources.append({"id":item.get("id"),"title":item.get("title") or "Fuente documental","applicability":a.get("applicability"),"subject_match":a.get("subject_match"),"task_match":a.get("task_match"),"scope_relation":a.get("scope_relation"),"source_object":a.get("source_object"),"supported_claims":claims[:5],"conditions":(a.get("conditions") or [])[:3]})
   if len(sources)>=3:break
  background=[{"id":x.get("id"),"title":x.get("title") or "Fuente relacionada","excerpt":x.get("text","")[:500],"status":"contextual" if x in contextual else "unassessed"} for x in (contextual+unassessed)[:4]]
  if not sources and decision.intent in {"procedural","troubleshooting","requirements"}:
   return self._unsupported_action_response(decision,state,background,"no_approved_evidence")
  if decision.intent=="conceptual" and sources and all(x.get("task_match") not in (None,"same","related") for x in sources):
   return self._partial_conceptual_response(state,sources,background,"no_definition_aligned_evidence")
  complete=bool((evidence.get("answer_completeness") or {}).get("complete_enough"))
  payload={"request":message,"current_intent":decision.intent,"case":state.to_dict(),"documented_sources":sources,"related_unverified_sources":background,"language":"match user","evidence_complete":complete,"policy":["Answer the exact requested scope first.","Synthesize all relevant excerpts, including multiple chunks from the same page.","Do not say information is absent if any excerpt contains it.","Do not tell the user to consult a document already present in document_evidence.","Never replace an internal documented procedure with a generic procedure.","Use complementary model knowledge only when evidence_complete is false, under a clear warning.","Ignore irrelevant UI, marketing, cover and contents excerpts.","Respond in the user's language.","Use concise bullets and at most five sections.","End every sentence.","Place [S#] after documented claims.","Documentation is primary. Cite only supported_claims from documented_sources using [S#].","Answer only what the selected claims support. If evidence is narrower than the request, explicitly say the evidence covers only that aspect.","Never claim that documentation lacks a definition or purpose merely because the selected excerpts are narrower; say that the selected evidence is partial.","For conceptual requests, prioritize claims that define purpose or capabilities over installation requirements, release notes, indexes or isolated component behavior.","If useful, add a short clearly labeled section 'Orientación general complementaria'.","State relevant restrictions and do not invent product-specific menus, logs, services, parameters or procedures.","Answer the current request and do not repeat an earlier fallback."],"response_contract":{"complete_over_comprehensive":True,"no_unfinished_sentence":True}}
  res=self.gateway.complete(LLMRequest([{"role":"system","content":"Act as a natural printing support assistant. Documentation is authoritative. Produce only the user-facing answer."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,default=str)}],"agent_core_v2_answer",self._budget(evidence),0.,None))
  if not res.ok:
   excerpts=[str(x.get("text") or "").strip() for x in approved[:3] if str(x.get("text") or "").strip()]
   return {"mode":"document_preserving_fallback","text":"No pude completar la redacción, pero conservé la evidencia recuperada.\n\n"+"\n\n".join(excerpts),"citations":citations,"knowledge_used":False,"error_code":getattr(res,"error_code",None)}
  text=res.text.strip();handled=False
  if res.finish_reason=="length":text=self._clean(text)+"\n\nRespuesta cerrada en el último punto completo por el límite temporal del proveedor.";handled=True
  used_ids=set(re.findall(r"\[(S\d+)\]",text));used=[x for x in citations if not used_ids or x.get("id") in used_ids]
  valid={x["id"] for x in sources if x.get("id")}
  if used_ids and not used_ids.issubset(valid):return self._evidence_recovery(decision,state,sources,background,"invalid_citations")
  knowledge_used=("orientación general complementaria" in text.casefold() or "conocimiento complementario" in text.casefold())
  return {"mode":"grounded" if approved and not knowledge_used else "grounded_plus_guarded_knowledge","text":text,"citations":used,"knowledge_used":knowledge_used,"internal_knowledge_used":knowledge_used,"unassessed_sources":[x.get("title") for x in unassessed],"provider":res.provider,"model":res.model,"usage":res.usage,"finish_reason":res.finish_reason,"truncation_handled":handled,"evidence_selection":{"original_approved_count":len(approved),"selected_count":len(sources),"selected_ids":[x["id"] for x in sources if x.get("id")]}}
 def _partial_conceptual_response(self,state,sources,background,reason):
  product=self._product_name(state);claims=[];citations=[]
  for source in sources:
   sid=source.get("id");citations.append(sid) if sid else None
   for claim in source.get("supported_claims") or []:
    value=" ".join(str(claim).split())
    if value and value not in claims:claims.append(value)
  text=(f"La evidencia seleccionada sobre {product} es parcial y describe funciones o componentes relacionados, "
        "pero no permite construir una definición general completa.\n\n### Aspectos documentados\n\n"+
        "\n".join(f"- {x} [{citations[min(i,len(citations)-1)]}]" if citations else f"- {x}" for i,x in enumerate(claims[:4]))+
        "\n\nPuedo continuar con una búsqueda documental más específica sin presentar estos componentes como si definieran todo el producto.")
  return {"mode":"partial_documented","text":text,"citations":sorted(set(citations)),"knowledge_used":False,"unassessed_sources":[x["title"] for x in background if x["status"]=="unassessed"],"fallback_reason":reason,"evidence_selection":{"selected_count":len(sources),"selected_ids":citations}}
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

=======


>>>>>>> 1c7283586f59a2e7b1c768d5d1196a5a0762c31f
