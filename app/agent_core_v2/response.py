from __future__ import annotations
import json,re,unicodedata
class ResponseComposer:
 def __init__(self,gateway=None,max_tokens=900):self.gateway=gateway;self.max_tokens=max(500,min(980,int(max_tokens)))
 def _product(self,state):
  names=[]
  for x in getattr(state.active_topic,"products",[]) or []:
   names.append(str(getattr(x,"canonical_name","") or getattr(x,"matched_text","") or "").strip())
  return ", ".join(x for x in names if x)
 def compose_conversation(self,message,decision,state):
  esc=getattr(state,"escalation",None);status=str(getattr(esc,"status","inactive") or "inactive");pending=getattr(esc,"pending_field",None);fields=dict(getattr(esc,"collected_fields",{}) or {});product=self._product(state)
  # Workflow responses must be anchored in canonical state, never generic cloud/business examples.
  if decision.intent=="escalation" or decision.conversation_act in {"escalation","cancel"}:
   if decision.conversation_act=="cancel" or decision.action=="cancel_escalation":
    return {"mode":"canonical_escalation","text":"Entendido. Cancelé el flujo de escalamiento y podemos continuar con el soporte del caso.","citations":[],"knowledge_used":False}
   if pending:
    label=str(pending).replace("_"," ")
    text=f"De acuerdo, prepararé el escalamiento{f' del caso de {product}' if product else ''}. Para continuar necesito: **{label}**."
   elif status not in {"inactive","closed","cancelled"}:
    text="El escalamiento está en curso. Continuemos con el siguiente dato solicitado por el caso."
   else:
    text=f"De acuerdo, iniciemos el escalamiento{f' del caso de {product}' if product else ' del caso actual'}. Cuéntame brevemente el problema, el impacto y qué validaciones ya se realizaron para no repetirlas."
   return {"mode":"canonical_escalation","text":text,"citations":[],"knowledge_used":False,"escalation_status":status,"pending_field":pending,"collected_fields":fields}
  if self.gateway is None:return {"mode":"conversation_pending","text":decision.clarification_question or "¿En qué puedo ayudarte?","citations":[],"knowledge_used":False}
  from app.llm_gateway.models import LLMRequest
  payload={"message":message,"conversation_act":decision.conversation_act,"intent":decision.intent,"active_product":product,"technical_case":state.technical_case.to_dict() if hasattr(state.technical_case,"to_dict") else {},"policy":["Respond naturally and briefly in Spanish.","Stay in printing technical support context.","Do not invent unrelated categories or examples.","Ask one precise question only when needed."]}
  res=self.gateway.complete(LLMRequest([{"role":"system","content":"You are the conversational layer of a printing support agent. Produce only the user-facing response."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,default=str)}],"agent_core_v2_conversation_response",min(self.max_tokens,240),0.,None))
  text=res.text.strip() if res.ok and res.finish_reason!="length" else decision.clarification_question or "Entendido. Continuemos con el caso."
  return {"mode":"natural_conversation" if res.ok else "safe_conversation_fallback","text":text,"citations":[],"knowledge_used":False,"provider":getattr(res,"provider",None),"model":getattr(res,"model",None),"usage":getattr(res,"usage",{}),"finish_reason":getattr(res,"finish_reason",None)}
 def _norm(self,v):return re.sub(r"[^a-z0-9]+"," ",unicodedata.normalize("NFKD",str(v or "")).encode("ascii","ignore").decode().casefold()).strip()
 def _terms(self,v):return {x for x in self._norm(v).split() if len(x)>2 and x not in {"que","como","para","por","del","los","las","una","con","sirve","necesita"}}
 def _rank(self,message,item):
  text=" ".join([item.get("title",""),item.get("text","")]);score=len(self._terms(message)&self._terms(text));a=item.get("semantic_assessment") or {};low=self._norm(item.get("text",""))
  if a.get("task_match")=="same":score+=3
  if "contents" in low or len(low)<170:score-=3
  return score
 def _citation(self,x):
  m=x.get("metadata") or {};return {"id":x.get("id"),"title":x.get("title"),"url":x.get("url"),"page":str(m.get("page_label") or m.get("page") or "")}
 def _budget(self,e):return min(self.max_tokens,900 if (e.get("answer_completeness") or {}).get("broad_request") else 620)
 def _closed_enough(self,text):
  v=str(text or "").rstrip();return bool(re.search(r'[.!?](?:\s|\]\s*)$',v)) and not v.endswith((':',';','-'))
 def _clean(self,text):
  v=str(text or "").strip();cuts=[v.rfind(x) for x in (". ",".\n","! ","!\n","? ","?\n")];cut=max(cuts) if cuts else -1
  if cut>=max(80,int(len(v)*.55)):v=v[:cut+1].rstrip()
  if v.count("**")%2:v=v.rsplit("**",1)[0].rstrip()
  return v
 def compose(self,message,decision,state,evidence):
  approved=(evidence.get("direct") or [])+(evidence.get("partial") or [])+(evidence.get("conditional") or []);unassessed=evidence.get("unassessed") or [];scope=(evidence.get("answer_completeness") or {}).get("request_scope","specific")
  ranked=sorted(approved,key=lambda x:self._rank(message,x),reverse=True);selected=ranked[:8 if scope=="broad" else 4]
  citations=[];seen=set()
  for x in selected:
   key=(x.get("url"),str((x.get("metadata") or {}).get("page_label") or (x.get("metadata") or {}).get("page")),x.get("chunk_fingerprint"))
   if key not in seen:seen.add(key);citations.append(self._citation(x))
  if self.gateway is None:return {"mode":"pending","text":"Respuesta pendiente.","citations":citations,"knowledge_used":False}
  from app.llm_gateway.models import LLMRequest
  sources=[]
  for x in selected:
   m=x.get("metadata") or {};sources.append({"id":x.get("id"),"title":x.get("title"),"page":m.get("page_label") or m.get("page"),"excerpt":str(x.get("text") or "")[:1450]})
  payload={"request":message,"request_scope":scope,"evidence":sources,"policy":["Give the direct answer in the first sentence.","For a specific question, answer only that dimension and omit adjacent requirements unless they are essential caveats.","Use documented evidence first with [S#] citations.","Do not claim that a web component is the locally installed monitor.","Do not infer exclusivity or comparisons against other editions unless documented.","Do not present every available feature as universally enabled; qualify platform-dependent capabilities.","For procedures, provide the common flow first and provider details only when useful.","Do not expose personal email addresses in the main answer unless the user explicitly asks for contact details; refer to the documented provider channel instead.","Respond naturally in Spanish, avoiding ceremonial introductions and repetitive summaries.","If the answer is already complete, stop. Never mention token limits or truncation to the user."],"contract":{"target_words":360 if scope=="broad" else 180,"max_sections":4,"complete_before_exhaustive":True}}
  res=self.gateway.complete(LLMRequest([{"role":"system","content":"Natural printing support assistant. Be accurate, grounded, concise and useful."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_answer",self._budget(evidence),0.,None))
  if not res.ok:return {"mode":"document_preserving_fallback","text":"No pude completar la redacción, pero conservé la evidencia recuperada.","citations":citations,"knowledge_used":False,"error_code":getattr(res,"error_code",None)}
  text=res.text.strip();handled=False
  if res.finish_reason=="length" and not self._closed_enough(text):text=self._clean(text);handled=True
  markers=set(re.findall(r"\[(S\d+)\]",text));used=[x for x in citations if not markers or x["id"] in markers]
  low=self._norm(text);knowledge=any(x in low for x in ("conocimiento general","conocimiento complementario","orientacion general complementaria","no en evidencia documentada"))
  return {"mode":"grounded_plus_guarded_knowledge" if knowledge else "grounded","text":text,"citations":used,"knowledge_used":knowledge,"internal_knowledge_used":knowledge,"unassessed_sources":[x.get("title") for x in unassessed],"provider":res.provider,"model":res.model,"usage":res.usage,"finish_reason":res.finish_reason,"truncation_handled":handled,"selected_evidence_ids":[x.get("id") for x in selected],"request_scope":scope,"answer_closed_naturally":self._closed_enough(text)}
