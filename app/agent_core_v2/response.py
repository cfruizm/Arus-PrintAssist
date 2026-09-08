from __future__ import annotations
import json,re

class ResponseComposer:
 def __init__(self,gateway=None,max_tokens=700):
  self.gateway=gateway;self.max_tokens=max(320,min(650,int(max_tokens)))
 def _citation(self,item):
  m=item.get("metadata") or {}
  return {"id":item.get("id"),"title":item.get("title"),"url":item.get("url"),"page":str(m.get("page_label") or m.get("page") or "")}
 def compose_conversation(self,message,decision,state):
  if decision.action in {"start_escalation","continue_escalation","resume_escalation"}:
   from .escalation_flow import NativeEscalationCoordinator
   coordinator=NativeEscalationCoordinator()
   text=coordinator.summary(state) if state.escalation.status=="ready" else (coordinator.question_for(state.escalation.pending_field) or "Continuemos con la información pendiente del escalamiento.")
   return {"mode":"native_escalation","text":text,"citations":[],"knowledge_used":False,"escalation_status":state.escalation.status,"pending_field":state.escalation.pending_field}
  if decision.action=="decline_out_of_scope":
   return {"mode":"out_of_scope","text":"Puedo ayudarte con soporte de impresión, sus plataformas, dispositivos y procesos relacionados. Si deseas continuar con el caso de impresión, cuéntame qué necesitas revisar.","citations":[],"knowledge_used":False}
  if decision.action=="ask_clarification" and decision.clarification_question:
   return {"mode":"clarification","text":decision.clarification_question,"citations":[],"knowledge_used":False}
  if decision.action=="cancel_all":
   return {"mode":"flow_cancelled","text":"El flujo actual fue cancelado. Podemos iniciar otra consulta cuando lo necesites.","citations":[],"knowledge_used":False}
  if self.gateway is None:
   return {"mode":"conversation_pending","text":decision.clarification_question or "¿En qué puedo ayudarte?","citations":[],"knowledge_used":False}
  from app.llm_gateway.models import LLMRequest
  payload={"message":message,"decision":decision.to_dict(),"state":state.to_dict(),"rules":["Respond briefly in Spanish.","Obey the canonical action.","Do not answer unrelated general knowledge when the action is clarification or out_of_scope.","Do not invent technical facts."]}
  res=self.gateway.complete(LLMRequest([{"role":"system","content":"You are the conversational layer of a printing support agent."},{"role":"user","content":json.dumps(payload,ensure_ascii=False)}],"agent_core_v2_conversation_response",180,0.,None))
  text=res.text.strip() if res.ok else decision.clarification_question or "Entendido. Podemos continuar con el caso."
  return {"mode":"natural_conversation" if res.ok else "safe_conversation_fallback","text":text,"citations":[],"knowledge_used":False,"provider":getattr(res,"provider",None),"model":getattr(res,"model",None),"usage":getattr(res,"usage",{}),"finish_reason":getattr(res,"finish_reason",None)}
 def _approved(self,evidence):
  items=[];seen=set()
  for key in ("direct","partial","conditional"):
   for item in evidence.get(key) or []:
    assessment=item.get("semantic_assessment") or {}
    claims=[" ".join(str(x).split()) for x in assessment.get("supported_claims") or [] if str(x).strip()]
    identity=str(item.get("url") or item.get("id"))
    if item.get("citable") and claims and identity not in seen:
     copy=dict(item);copy["supported_claims"]=claims[:4];items.append(copy);seen.add(identity)
  return items[:3]
 def compose(self,message,decision,state,evidence):
  if self.gateway is None:return {"mode":"pending","text":"Respuesta pendiente.","citations":[],"knowledge_used":False}
  from app.llm_gateway.models import LLMRequest
  approved=self._approved(evidence);unassessed=evidence.get("unassessed") or []
  sources=[{"id":x.get("id"),"title":x.get("title"),"claims":x.get("supported_claims"),"applicability":(x.get("semantic_assessment") or {}).get("applicability")} for x in approved]
  has_evidence=bool(sources)
  if has_evidence:
   mode="grounded";budget=min(self.max_tokens,420)
   rules=["Use only claims supplied in sources for documented statements.","Cite every documented paragraph with [S#].","If sources cover only part of the request, say so in one sentence.","Optional general guidance must be under the exact heading 'Orientación complementaria, no confirmada por las fuentes recuperadas'.","Do not invent menus, fields, commands, compatibility values or exact procedures.","Answer in Spanish, concisely, and finish within the budget."]
  else:
   mode="guarded_internal_knowledge";budget=min(self.max_tokens,260)
   rules=["There is no approved documentary evidence for this request.","Start with the exact warning 'Orientación complementaria, no confirmada por las fuentes recuperadas'.","Provide useful but cautious general orientation.","Do not describe the answer as documented or grounded.","Do not invent exact menus, fields, commands, compatibility values or product-specific procedures.","Prefer safe checks, options and one clarifying question when exact context is required.","Answer in Spanish and finish within the budget."]
  payload={"request":message,"intent":decision.intent,"state":state.to_dict(),"sources":sources,"rules":rules}
  res=self.gateway.complete(LLMRequest([{"role":"system","content":"Natural printing support assistant. Evidence integrity is mandatory."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_answer",budget,0.,None))
  if not res.ok:
   text=("No pude completar la redacción con la evidencia disponible." if has_evidence else "Orientación complementaria, no confirmada por las fuentes recuperadas: necesito precisar el entorno o módulo para sugerir opciones seguras sin inventar un procedimiento.")
   return {"mode":"document_preserving_fallback" if has_evidence else mode,"text":text,"citations":[],"knowledge_used":not has_evidence,"internal_knowledge_used":not has_evidence,"internal_knowledge_warning_shown":not has_evidence,"selected_evidence_ids":[x["id"] for x in sources]}
  text=res.text.strip()
  marker_ids=set(re.findall(r"\[(S\d+)\]",text));valid={x["id"] for x in sources};invalid=marker_ids-valid
  if invalid or (has_evidence and not marker_ids):
   claims=[]
   for source in sources:
    claims.extend(f"- {claim} [{source['id']}]" for claim in source["claims"][:2])
   text="Información documentada disponible:\n"+"\n".join(claims)
   marker_ids=valid
  bounded=any((x.get("semantic_assessment") or {}).get("applicability") in {"partial","conditional"} for x in approved)
  knowledge=(not has_evidence) or bounded
  final_mode=("grounded_plus_guarded_knowledge" if has_evidence and knowledge else mode)
  return {"mode":final_mode,"text":text,"citations":[self._citation(x) for x in approved if x.get("id") in marker_ids],"knowledge_used":knowledge,"internal_knowledge_used":knowledge,"internal_knowledge_warning_shown":knowledge,"unassessed_sources":[x.get("title") for x in unassessed],"provider":res.provider,"model":res.model,"usage":res.usage,"finish_reason":res.finish_reason,"truncation_handled":False,"selected_evidence_ids":[x["id"] for x in sources],"request_scope":(evidence.get("answer_completeness") or {}).get("request_scope","specific")}
