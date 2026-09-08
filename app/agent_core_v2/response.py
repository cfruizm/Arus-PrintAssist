from __future__ import annotations
import json,re
class ResponseComposer:
 def __init__(self,gateway=None,max_tokens=700):self.gateway=gateway;self.max_tokens=max(320,min(720,int(max_tokens)))
 def compose_conversation(self,message,decision,state):
  if self.gateway is None:return {"mode":"conversation_pending","text":decision.clarification_question or "¿En qué puedo ayudarte?","citations":[],"knowledge_used":False}
  from app.llm_gateway.models import LLMRequest
  payload={"message":message,"conversation_act":decision.conversation_act,"state":state.to_dict(),"policy":["Respond naturally and briefly in the user's language.","Use only canonical escalation state.","Ask one precise clarification when needed."]}
  res=self.gateway.complete(LLMRequest([{"role":"system","content":"You are the conversational layer of a printing support agent."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,default=str)}],"agent_core_v2_conversation_response",min(self.max_tokens,220),0.,None))
  text=res.text.strip() if res.ok and res.finish_reason!="length" else decision.clarification_question or "Entendido. Podemos continuar con el caso."
  return {"mode":"natural_conversation" if res.ok else "safe_conversation_fallback","text":text,"citations":[],"knowledge_used":False,"provider":getattr(res,"provider",None),"model":getattr(res,"model",None),"usage":getattr(res,"usage",{}),"finish_reason":getattr(res,"finish_reason",None)}
 def _citation(self,item):
  m=item.get("metadata") or {};return {"id":item.get("id"),"title":item.get("title"),"url":item.get("url"),"page":str(m.get("page_label") or m.get("page") or "")}
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
  sources=[]
  for item in approved[:12]:
   a=item.get("semantic_assessment") or {};m=item.get("metadata") or {}
   sources.append({"id":item.get("id"),"title":item.get("title"),"page":m.get("page_label") or m.get("page"),"applicability":a.get("applicability"),"excerpt":str(item.get("text") or "")[:2200]})
  background=[{"id":x.get("id"),"title":x.get("title"),"excerpt":str(x.get("text") or "")[:1000],"status":"contextual" if x in contextual else "unassessed"} for x in (contextual+unassessed)[:4]]
  complete=bool((evidence.get("answer_completeness") or {}).get("complete_enough"))
  payload={"request":message,"language":"match user","document_evidence":sources,"related_unverified_sources":background,"evidence_complete":complete,"policy":["Answer the exact requested scope first.","Synthesize all relevant excerpts, including multiple chunks from the same page.","Do not say information is absent if any excerpt contains it.","Do not tell the user to consult a document already present in document_evidence.","Never replace an internal documented procedure with a generic procedure.","Use complementary model knowledge only when evidence_complete is false, under a clear warning.","Ignore irrelevant UI, marketing, cover and contents excerpts.","Respond in the user's language.","Use concise bullets and at most five sections.","End every sentence.","Place [S#] after documented claims."],"response_contract":{"complete_over_comprehensive":True,"no_unfinished_sentence":True}}
  res=self.gateway.complete(LLMRequest([{"role":"system","content":"You are a natural technical support assistant. Documentation is authoritative. Produce only the user-facing answer."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,default=str)}],"agent_core_v2_answer",self._budget(evidence),0.,None))
  if not res.ok:
   excerpts=[str(x.get("text") or "").strip() for x in approved[:3] if str(x.get("text") or "").strip()]
   return {"mode":"document_preserving_fallback","text":"No pude completar la redacción, pero conservé la evidencia recuperada.\n\n"+"\n\n".join(excerpts),"citations":citations,"knowledge_used":False,"error_code":getattr(res,"error_code",None)}
  text=res.text.strip();handled=False
  if res.finish_reason=="length":text=self._clean(text)+"\n\nRespuesta cerrada en el último punto completo por el límite temporal del proveedor.";handled=True
  used_ids=set(re.findall(r"\[(S\d+)\]",text));used=[x for x in citations if not used_ids or x.get("id") in used_ids]
  knowledge_used=("orientación general complementaria" in text.casefold() or "conocimiento complementario" in text.casefold())
  return {"mode":"grounded" if approved and not knowledge_used else "grounded_plus_guarded_knowledge","text":text,"citations":used,"knowledge_used":knowledge_used,"internal_knowledge_used":knowledge_used,"unassessed_sources":[x.get("title") for x in unassessed],"provider":res.provider,"model":res.model,"usage":res.usage,"finish_reason":res.finish_reason,"truncation_handled":handled}
