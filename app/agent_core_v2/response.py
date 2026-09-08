from __future__ import annotations
import json,re,unicodedata
class ResponseComposer:
 def __init__(self,gateway=None,max_tokens=700):self.gateway=gateway;self.max_tokens=max(420,min(760,int(max_tokens)))
 def compose_conversation(self,message,decision,state):
  if self.gateway is None:return {"mode":"conversation_pending","text":decision.clarification_question or "¿En qué puedo ayudarte?","citations":[],"knowledge_used":False}
  from app.llm_gateway.models import LLMRequest
  res=self.gateway.complete(LLMRequest([{"role":"system","content":"Respond naturally and briefly in the user's language."},{"role":"user","content":message}],"agent_core_v2_conversation_response",220,0.,None));text=res.text.strip() if res.ok else decision.clarification_question or "Entendido. Podemos continuar."
  return {"mode":"natural_conversation" if res.ok else "safe_conversation_fallback","text":text,"citations":[],"knowledge_used":False,"provider":getattr(res,"provider",None),"model":getattr(res,"model",None),"usage":getattr(res,"usage",{}),"finish_reason":getattr(res,"finish_reason",None)}
 def _norm(self,v):return re.sub(r"[^a-z0-9]+"," ",unicodedata.normalize("NFKD",str(v or "")).encode("ascii","ignore").decode().casefold()).strip()
 def _terms(self,v):return {x for x in self._norm(v).split() if len(x)>2 and x not in {"que","como","para","por","del","los","las","una","con","sirve","necesita"}}
 def _rank(self,message,item):
  text=" ".join([item.get("title",""),item.get("text","")]);score=len(self._terms(message)&self._terms(text));a=item.get("semantic_assessment") or {}
  if a.get("task_match")=="same":score+=3
  low=self._norm(item.get("text",""));
  if "contents" in low or len(low)<170:score-=3
  return score
 def _citation(self,x):
  m=x.get("metadata") or {};return {"id":x.get("id"),"title":x.get("title"),"url":x.get("url"),"page":str(m.get("page_label") or m.get("page") or "")}
 def _budget(self,e):return min(self.max_tokens,720 if (e.get("answer_completeness") or {}).get("broad_request") else 500)
 def _clean(self,text):
  v=str(text or "").strip();cuts=[v.rfind(x) for x in (". ",".\n","! ","!\n","? ","?\n")];cut=max(cuts) if cuts else -1
  if cut>=max(80,int(len(v)*.55)):v=v[:cut+1].rstrip()
  if v.count("**")%2:v=v.rsplit("**",1)[0].rstrip()
  return v
 def compose(self,message,decision,state,evidence):
  approved=(evidence.get("direct") or [])+(evidence.get("partial") or [])+(evidence.get("conditional") or []);unassessed=evidence.get("unassessed") or []
  ranked=sorted(approved,key=lambda x:self._rank(message,x),reverse=True);scope=(evidence.get("answer_completeness") or {}).get("request_scope","specific");selected=ranked[:8 if scope=="broad" else 5]
  citations=[];seen=set()
  for x in selected:
   key=(x.get("url"),str((x.get("metadata") or {}).get("page_label") or (x.get("metadata") or {}).get("page")),x.get("chunk_fingerprint"))
   if key not in seen:seen.add(key);citations.append(self._citation(x))
  from app.llm_gateway.models import LLMRequest
  sources=[]
  for x in selected:
   m=x.get("metadata") or {};sources.append({"id":x.get("id"),"title":x.get("title"),"page":m.get("page_label") or m.get("page"),"excerpt":str(x.get("text") or "")[:1500]})
  payload={"request":message,"request_scope":scope,"evidence":sources,"policy":["Answer only the scope asked by the user. Do not add adjacent categories to a specific question.","For broad procedures, cover the complete flow but compress provider-specific variants after the common steps.","Use documented evidence first and add [S#] citations.","Never say no documentation was provided when evidence is non-empty.","If evidence is empty or incomplete, clearly label complementary model knowledge.","Respond in the user's language.","Use at most four short sections and finish with a complete sentence.","Do not spend the ending on a long list of URLs, ports, variants or contacts unless the user explicitly asked for that detail."],"contract":{"target_words":420 if scope=="broad" else 220,"complete_before_exhaustive":True}}
  res=self.gateway.complete(LLMRequest([{"role":"system","content":"Natural technical support assistant. Be grounded, focused and complete."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_answer",self._budget(evidence),0.,None))
  if not res.ok:return {"mode":"document_preserving_fallback","text":"No pude completar la redacción, pero conservé la evidencia recuperada.","citations":citations,"knowledge_used":False,"error_code":getattr(res,"error_code",None)}
  text=res.text.strip();handled=False
  if res.finish_reason=="length":text=self._clean(text)+"\n\nLa respuesta fue cerrada en el último punto completo por el límite de salida.";handled=True
  marker_ids=set(re.findall(r"\[(S\d+)\]",text));used=[x for x in citations if not marker_ids or x["id"] in marker_ids]
  lower=self._norm(text);knowledge=any(x in lower for x in ("conocimiento general","conocimiento complementario","orientacion general complementaria","no en evidencia documentada"))
  return {"mode":"grounded_plus_guarded_knowledge" if knowledge else "grounded","text":text,"citations":used,"knowledge_used":knowledge,"internal_knowledge_used":knowledge,"unassessed_sources":[x.get("title") for x in unassessed],"provider":res.provider,"model":res.model,"usage":res.usage,"finish_reason":res.finish_reason,"truncation_handled":handled,"selected_evidence_ids":[x.get("id") for x in selected],"request_scope":scope}
