from __future__ import annotations
import json,re

class ResponseComposer:
 def __init__(self,gateway=None,max_tokens=700):self.gateway=gateway;self.max_tokens=max(360,min(650,int(max_tokens)))
 def _citation(self,x):
  m=x.get("metadata") or {};return {"id":x.get("id"),"title":x.get("title"),"url":x.get("url"),"page":str(m.get("page_label") or m.get("page") or "")}
 def compose_conversation(self,message,decision,state,plan=None):
  if decision.action in {"start_escalation","continue_escalation","resume_escalation"}:
   from .escalation_flow import NativeEscalationCoordinator
   c=NativeEscalationCoordinator();text=c.summary(state) if state.escalation.status=="ready" else c.question_for(state.escalation.pending_field) or "Continuemos con el dato pendiente."
   return {"mode":"native_escalation","text":text,"citations":[],"knowledge_used":False}
  if decision.action=="decline_out_of_scope":return {"mode":"out_of_scope","text":"Ese tema está fuera de mi alcance de soporte de impresión. Si quieres, continuamos con el caso técnico que estábamos revisando.","citations":[],"knowledge_used":False}
  if decision.action=="cancel_all":return {"mode":"flow_cancelled","text":"Listo, cancelé el flujo actual. ¿Qué necesitas revisar ahora?","citations":[],"knowledge_used":False}
  if self.gateway is None:return {"mode":"clarification","text":decision.clarification_question or "¿Qué dato puedes ampliar?","citations":[],"knowledge_used":False}
  from app.llm_gateway.models import LLMRequest
  payload={"message":message,"decision":decision.to_dict(),"state":state.to_dict(),"plan":plan.to_dict() if plan else {},"instructions":["Act as a natural printing support colleague, not as a policy or documentation auditor.","Respond to the current message in Spanish and use active context only when relevant.","If clarification is needed, acknowledge what you understood and ask exactly one useful question.","Do not repeat a generic clarification when the message is self-contained.","Keep the response under 90 words."]}
  r=self.gateway.complete(LLMRequest([{"role":"system","content":"Natural conversational layer for an enterprise printing support agent."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_conversation_response",180,0.,None))
  text=r.text.strip() if r.ok else decision.clarification_question or "Entendido. ¿Qué detalle puedes ampliar para continuar?"
  return {"mode":"natural_conversation" if r.ok else "safe_conversation_fallback","text":text,"citations":[],"knowledge_used":False,"provider":getattr(r,"provider",None),"model":getattr(r,"model",None),"usage":getattr(r,"usage",{}),"finish_reason":getattr(r,"finish_reason",None)}
 def _approved(self,e):
  out=[];seen=set()
  for key in ("direct","partial","conditional"):
   for x in e.get(key) or []:
    a=x.get("semantic_assessment") or {};claims=[" ".join(str(v).split()) for v in a.get("supported_claims") or [] if str(v).strip()];ident=str(x.get("url") or x.get("id"))
    if x.get("citable") and claims and ident not in seen:
     y=dict(x);y["claims"]=claims[:4];out.append(y);seen.add(ident)
  return out[:3]
 def compose(self,message,decision,state,evidence,plan=None):
  if self.gateway is None:return {"mode":"pending","text":"Respuesta pendiente.","citations":[],"knowledge_used":False}
  from app.llm_gateway.models import LLMRequest
  approved=self._approved(evidence);has=bool(approved);bounded=any((x.get("semantic_assessment") or {}).get("applicability")!="direct" for x in approved)
  sources=[{"id":x.get("id"),"title":x.get("title"),"claims":x["claims"],"applicability":(x.get("semantic_assessment") or {}).get("applicability")} for x in approved]
  instructions=["Behave like a capable, natural printing support colleague.","Answer the user's need first. Never lead with a report about evidence coverage.","Use approved source claims for documented statements and cite them with [S#].","You may add useful general model knowledge when sources are partial or absent, but never present exact menus, values, commands or sensitive changes as confirmed.","When complementary knowledge materially affects the answer, disclose it in one short natural sentence. Do not use a repeated heading or policy boilerplate.","For a vague procedure, name plausible categories only to clarify the user's goal, then ask one precise question.","For troubleshooting, acknowledge the failure, use known case facts, and ask the single most useful missing diagnostic question.","Do not tell the user merely to consult documentation or contact support unless that is the only safe next step.","Avoid generic numbered checklists. Keep the response under 130 words and finish completely."]
  payload={"request":message,"intent":decision.intent,"case":state.to_dict(),"conversation_plan":plan.to_dict() if plan else {},"approved_sources":sources,"instructions":instructions}
  r=self.gateway.complete(LLMRequest([{"role":"system","content":"Enterprise printing support assistant. Natural help first; evidence integrity remains mandatory."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_answer",min(self.max_tokens,300),0.,None))
  if not r.ok:
   text="No pude completar la respuesta. Cuéntame el punto exacto en el que se presenta el problema y continuamos desde ahí."
   return {"mode":"safe_conversational_fallback","text":text,"citations":[],"knowledge_used":not has,"internal_knowledge_used":not has,"internal_knowledge_warning_shown":False,"selected_evidence_ids":[x["id"] for x in sources]}
  text=r.text.strip();markers=set(re.findall(r"\[(S\d+)\]",text));valid={x["id"] for x in sources}
  if markers-valid:markers=set()
  if has and not markers:
   claim=sources[0]["claims"][0];text=f"{claim} [{sources[0]['id']}]\n\n"+text;markers={sources[0]["id"]}
  knowledge=(not has) or bounded
  mode="grounded" if has and not knowledge else "grounded_plus_guarded_knowledge" if has else "guarded_internal_knowledge"
  return {"mode":mode,"text":text,"citations":[self._citation(x) for x in approved if x.get("id") in markers],"knowledge_used":knowledge,"internal_knowledge_used":knowledge,"internal_knowledge_warning_shown":knowledge,"unassessed_sources":[x.get("title") for x in evidence.get("unassessed") or []],"provider":r.provider,"model":r.model,"usage":r.usage,"finish_reason":r.finish_reason,"truncation_handled":False,"selected_evidence_ids":[x["id"] for x in sources],"conversation_plan":plan.to_dict() if plan else {}}
