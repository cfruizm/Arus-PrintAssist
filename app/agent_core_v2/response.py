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
  if self.gateway is None:return {"mode":"clarification","text":decision.clarification_question or "¿Qué dato puedes ampliar para continuar?","citations":[],"knowledge_used":False}
  from app.llm_gateway.models import LLMRequest
  payload={"message":message,"decision":decision.to_dict(),"state":state.to_dict(),"plan":plan.to_dict() if plan else {},"rules":["Respond briefly in Spanish as a natural printing support colleague.","Use active context only when relevant.","If clarification is needed, acknowledge what is understood and ask one useful question.","Never answer unrelated general knowledge."]}
  r=self.gateway.complete(LLMRequest([{"role":"system","content":"Conversational layer for enterprise printing support."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_conversation_response",180,0.,None))
  return {"mode":"natural_conversation" if r.ok else "safe_conversation_fallback","text":r.text.strip() if r.ok else decision.clarification_question or "¿Qué detalle puedes ampliar?","citations":[],"knowledge_used":False,"provider":getattr(r,"provider",None),"model":getattr(r,"model",None),"usage":getattr(r,"usage",{}),"finish_reason":getattr(r,"finish_reason",None)}
 def _approved(self,e):
  out=[];seen=set()
  for key in ("direct","partial","conditional"):
   for x in e.get(key) or []:
    a=x.get("semantic_assessment") or {};claims=[" ".join(str(v).split()) for v in a.get("supported_claims") or [] if str(v).strip()];ident=str(x.get("url") or x.get("id"))
    if x.get("citable") and claims and ident not in seen:y=dict(x);y["claims"]=claims[:4];out.append(y);seen.add(ident)
  return out[:3]
 def _unsupported_precision(self,text,exact_allowed):
  if exact_allowed:return False
  t=str(text or "")
  route=bool(re.search(r"\b[^\n]{2,35}\s*(?:>|→|/)\s*[^\n]{2,35}",t))
  ui_sequence=len(re.findall(r"(?:selecciona|haz clic|navega|ve a|abre|activa|desactiva|establece|ingresa)\b",t,re.I))>=2
  exact_field=bool(re.search(r"(?:bot[oó]n|pesta[nñ]a|campo|men[uú]|opci[oó]n)\s+[\"'*]{0,2}[A-ZÁÉÍÓÚÑ][^.,\n]{1,35}",t,re.I))
  commands=bool(re.search(r"(?:^|\n)\s*(?:sudo|curl|python|pip|docker|kubectl|powershell|cmd)\b",t,re.I))
  return route or ui_sequence or exact_field or commands
 def _generate(self,payload,budget,purpose):
  from app.llm_gateway.models import LLMRequest
  return self.gateway.complete(LLMRequest([{"role":"system","content":"Natural enterprise printing support. Follow the executable conversation plan exactly."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],purpose,budget,0.,None))
 def compose(self,message,decision,state,evidence,plan=None):
  approved=self._approved(evidence);has=bool(approved);sources=[{"id":x.get("id"),"title":x.get("title"),"claims":x["claims"],"applicability":(x.get("semantic_assessment") or {}).get("applicability")} for x in approved];pd=plan.to_dict() if plan else {};exact=bool(pd.get("exact_operational_details_allowed"))
  rules=["Answer the need first in Spanish, naturally and in at most 110 words.","Documented statements use only approved claims and [S#].","General knowledge may orient, but unsupported exact menus, fields, commands, paths, values or product procedures are forbidden.","If strategy is clarify_then_guide, do not provide steps: explain the ambiguity briefly and ask exactly one discriminating question.","If strategy is diagnose, acknowledge the failure and ask exactly one missing diagnostic question.","Do not lead with evidence-policy language and do not use generic checklists."]
  payload={"request":message,"intent":decision.intent,"case":state.to_dict(),"plan":pd,"approved_sources":sources,"rules":rules}
  r=self._generate(payload,min(self.max_tokens,270),"agent_core_v2_answer")
  if not r.ok:return {"mode":"safe_conversational_fallback","text":"Cuéntame el punto exacto en el que se presenta el problema y continuamos desde ahí.","citations":[],"knowledge_used":not has,"selected_evidence_ids":[x["id"] for x in sources]}
  text=r.text.strip();regenerated=False
  if self._unsupported_precision(text,exact):
   payload["rules"]=["The previous draft contained unsupported operational precision.","Do not provide any menu, field, command, route, value or step.","Acknowledge the goal, briefly explain what must be distinguished, and ask exactly one useful question in Spanish under 75 words."]
   r2=self._generate(payload,170,"agent_core_v2_safe_regeneration")
   text=r2.text.strip() if r2.ok else "Para orientarte sin asumir una configuración incorrecta, necesito precisar el tipo de operación y el entorno donde la realizas. ¿Qué resultado esperas obtener y en qué módulo estás trabajando?";regenerated=True
  markers=set(re.findall(r"\[(S\d+)\]",text));valid={x["id"] for x in sources};markers&=valid
  knowledge=(not has) or any((x.get("semantic_assessment") or {}).get("applicability")!="direct" for x in approved)
  mode="grounded" if has and not knowledge else "grounded_plus_guarded_knowledge" if has else "guarded_internal_knowledge"
  return {"mode":mode,"text":text,"citations":[self._citation(x) for x in approved if x.get("id") in markers],"knowledge_used":knowledge,"internal_knowledge_used":knowledge,"internal_knowledge_warning_shown":knowledge,"unassessed_sources":[x.get("title") for x in evidence.get("unassessed") or []],"provider":r.provider,"model":r.model,"usage":r.usage,"finish_reason":r.finish_reason,"selected_evidence_ids":[x["id"] for x in sources],"conversation_plan":pd,"unsupported_precision_regenerated":regenerated}
