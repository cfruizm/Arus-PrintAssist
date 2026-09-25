from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Callable,Any
import hashlib,json,re,unicodedata
from .exact_document_retrieval import document_identifiers,query_variants,exact_matches
@dataclass
class RetrievalQuery:
 text:str;fields:dict[str,Any];fingerprint:str
 def to_dict(self):return asdict(self)
def _text(value):
 if value is None:return ""
 if isinstance(value,str):return value
 if isinstance(value,(int,float,bool)):return str(value)
 if isinstance(value,list):return " ".join(_text(x) for x in value if _text(x))
 if isinstance(value,dict):
  for key in ("summary","subject","operation","product","value","text"):
   if value.get(key) is not None:return _text(value.get(key))
  return ""
 return str(value)
class RetrievalQueryBuilder:
 def build(self,message,memory,understanding):
  details={str(k):_text(v) for k,v in memory.pending_goal.known_details.items() if _text(v).strip()}
  user_act=str(getattr(understanding,"user_act","") or "");topic_relation=str(getattr(understanding,"topic_relation","") or "")
  contextual_operation=str(message or "").strip() if user_act in {"follow_up","answer_to_question","reported_failure","attempt_result"} or topic_relation=="same_topic" else ""
  fields={"goal":memory.pending_goal.summary or understanding.current_goal,"intent":memory.pending_goal.intent or understanding.intent,"details":details,"symptoms":list(memory.support_case.symptoms),"observations":list(memory.support_case.observations[-3:]),"affected_scope":memory.support_case.affected_scope,"current_message":message,"contextual_operation":contextual_operation or None,"user_act":user_act,"topic_relation":topic_relation}
  parts=[str(message or "").strip(),_text(fields["goal"]).strip()]
  if contextual_operation and contextual_operation.casefold()!=_text(fields["goal"]).strip().casefold():parts.append(contextual_operation)
  parts += [f"{k}: {v}" for k,v in details.items()]+fields["symptoms"]+fields["observations"]
  if fields["affected_scope"]:parts.append(f"alcance: {fields['affected_scope']}")
  text=". ".join(dict.fromkeys(x for x in parts if x))[:1200];fingerprint=hashlib.sha256(json.dumps(fields,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20]
  return RetrievalQuery(text,fields,fingerprint)
 def current_only(self,message,understanding):
  fields={"goal":understanding.current_goal,"intent":understanding.intent,"details":dict(understanding.goal_updates or {}),"symptoms":[],"observations":[],"affected_scope":None,"current_message":message,"context_mode":"current_turn_only","grounded_only":True}
  text=". ".join(dict.fromkeys(x for x in [str(understanding.current_goal or ""),str(message or "")]+[str(v) for v in fields["details"].values()] if x))[:900]
  return RetrievalQuery(text,fields,hashlib.sha256(json.dumps(fields,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20])
def _tokens(text):
 text=unicodedata.normalize("NFKD",str(text or "")).encode("ascii","ignore").decode().casefold();stop={"como","para","que","con","del","las","los","una","uno","por","the","and","from","this","realizar","explicar"}
 return {x for x in re.findall(r"[a-z0-9_]{3,}",text) if x not in stop}
def _quality(message,evidence):
 wanted=_tokens(message)
 if not wanted:return 0.0
 return round(max([len(wanted&_tokens((x.get("title") or "")+" "+(x.get("text") or "")))/len(wanted) for x in evidence] or [0.0]),4)
def _page(e):
 m=e.get("metadata") or {};raw=m.get("page_label") or m.get("page") or e.get("page") or 0
 try:return int(str(raw).strip())
 except:return 10**9
def _identity(e):return str(e.get("url") or e.get("source") or (e.get("metadata") or {}).get("source") or e.get("title") or "")
def _normalize_items(items):
 out=[]
 for i,x in enumerate(items or [],1):
  m=dict(x.get("metadata") or {});out.append({"id":f"R{i}","title":str(x.get("title") or m.get("title") or "Fuente sin título"),"source":str(x.get("source") or m.get("source") or ""),"url":str(x.get("url") or m.get("source_url") or m.get("canonical_url") or ""),"score":x.get("score"),"page":str(m.get("page_label") or m.get("page") or ""),"text":str(x.get("text") or "")[:1800],"metadata":m})
 return out
def _expand_procedure(query,evidence,k=8):
 if not evidence:return evidence,{"enabled":True,"attempted":False,"reason":"no_seed_evidence","llm_called":False}
 seed=evidence[0];source=_identity(seed)
 if not source:return evidence,{"enabled":True,"attempted":False,"reason":"seed_without_identity","llm_called":False}
 try:
  from app.integration.document_expansion_adapter import retrieve_same_document
  raw=retrieve_same_document(query,source,k)
 except Exception as exc:return evidence,{"enabled":True,"attempted":True,"ok":False,"llm_called":False,"errors":[f"{type(exc).__name__}: {exc}"]}
 expanded=_normalize_items(raw.get("evidence") or [])
 merged=[];seen=set()
 for x in evidence+expanded:
  key=(_identity(x),_page(x),hashlib.sha256(str(x.get("text") or "").casefold().encode()).hexdigest()[:12])
  if key not in seen:seen.add(key);merged.append(x)
 same=[x for x in merged if _identity(x)==source];same.sort(key=_page)
 selected=same[:k] if same else evidence[:k]
 for i,x in enumerate(selected,1):x["id"]=f"R{i}"
 pages=[x.get("page") for x in selected if x.get("page")]
 return selected,{"enabled":True,"attempted":True,"ok":bool(raw.get("ok")),"llm_called":False,"adapter":raw.get("adapter"),"seed_document":source,"seed_page":seed.get("page"),"pages":pages,"count":len(selected),"ordered":True,"same_document_only":all(_identity(x)==source for x in selected),"errors":raw.get("errors") or [],"generation_enabled":False}
class ReadOnlyRetrieval:
 def __init__(self,retrieve_fn:Callable|None=None,k=6):self.retrieve_fn=retrieve_fn or self._existing;self.k=max(1,min(10,int(k)))
 def _existing(self,query,k):
  from app.integration.lab_retrieval_adapter import retrieve_from_existing_backend
  return retrieve_from_existing_backend(query,k)
 def _normalize(self,raw):return _normalize_items(raw.get("evidence") or [])
 def search(self,built,current_only=None,preferred_sources=None):
  preferred_sources=[str(x) for x in (preferred_sources or []) if str(x).strip()]
  fields=built.fields or {};details=fields.get("details") or {};subject=details.get("subject") or details.get("product") or "";identifiers=document_identifiers(fields.get("current_message"),fields.get("goal"),subject);variants=query_variants(fields.get("current_message"),fields.get("goal"),subject)
  if identifiers and variants:
   attempts=[];matched=[];raw_last={}
   for variant in variants:
    raw=self.retrieve_fn(variant,max(self.k,12)) or {};raw_last=raw;rows=self._normalize(raw);hits=exact_matches(rows,identifiers);attempts.append({"mode":"exact_document_identifier","query_text":variant,"count":len(rows),"exact_match_count":len(hits),"titles":[x.get("title") for x in rows[:5]],"sources":[x.get("source") for x in rows[:5]]})
    matched.extend(hits)
    if hits:break
   if matched:
    seen=set();seed=[]
    for item in matched:
     key=(_identity(item),item.get("page"),str(item.get("text") or "")[:240])
     if key not in seen:seen.add(key);seed.append(item)
    expansion_query=". ".join(dict.fromkeys(x for x in [str(fields.get("current_message") or ""),str(fields.get("goal") or ""),str(subject or "")] if x))
    evidence,expansion=_expand_procedure(expansion_query,seed,24)
    groups={}
    for x in evidence:
     identity=_identity(x);g=groups.setdefault(identity,{"identity":identity,"title":x["title"],"pages":[],"chunks":0});g["chunks"]+=1
     if x["page"] and x["page"] not in g["pages"]:g["pages"].append(x["page"])
    return {"enabled":True,"llm_called":False,"production_changed":False,"query":built.to_dict(),"ok":True,"adapter":raw_last.get("adapter"),"count":len(evidence),"evidence":evidence,"document_groups":list(groups.values()),"errors":[],"diagnostic_only":True,"selection":{"chosen_mode":"exact_document_identifier","quality":1.0,"attempts":attempts,"context_contamination_avoided":True,"exact_identifier_match":True,"matched_identifiers":identifiers},"procedural_expansion":expansion,"exact_document_match":{"matched":True,"identifiers":identifiers,"source":_identity(evidence[0]) if evidence else None}}
   return {"enabled":True,"llm_called":False,"production_changed":False,"query":built.to_dict(),"ok":bool(raw_last.get("ok")),"adapter":raw_last.get("adapter"),"count":0,"evidence":[],"document_groups":[],"errors":raw_last.get("errors") or [],"diagnostic_only":True,"selection":{"chosen_mode":"exact_document_identifier","quality":0.0,"attempts":attempts,"context_contamination_avoided":True,"exact_identifier_match":False,"matched_identifiers":identifiers},"procedural_expansion":{"enabled":False,"reason":"exact_document_not_found","attempted":False},"exact_document_match":{"matched":False,"identifiers":identifiers,"source":None}}
  preferred_attempt=None
  if current_only is not None and preferred_sources:
   try:
    from app.integration.document_expansion_adapter import retrieve_same_document
    source=preferred_sources[0];rawp=retrieve_same_document(current_only.text,source,self.k) or {};ep=self._normalize(rawp);qp=_quality(current_only.fields.get("current_message"),ep)
    preferred_attempt={"mode":"active_document","query":current_only.to_dict(),"source":source,"quality":qp,"count":len(ep)}
    if ep and qp>=0.30:
     limit=18 if str(current_only.fields.get("intent") or "")=="requirements" else 8;ep,exp=_expand_procedure(current_only.text,ep,limit);groups={}
     for x in ep:
      identity=_identity(x);g=groups.setdefault(identity,{"identity":identity,"title":x["title"],"pages":[],"chunks":0});g["chunks"]+=1
      if x["page"] and x["page"] not in g["pages"]:g["pages"].append(x["page"])
     return {"enabled":True,"llm_called":False,"production_changed":False,"query":current_only.to_dict(),"ok":bool(rawp.get("ok",True)),"adapter":rawp.get("adapter"),"count":len(ep),"evidence":ep,"document_groups":list(groups.values()),"errors":rawp.get("errors") or [],"diagnostic_only":True,"selection":{"chosen_mode":"active_document","quality":qp,"attempts":[preferred_attempt],"context_contamination_avoided":True,"active_document_reused":True},"procedural_expansion":exp}
   except Exception as exc:preferred_attempt={"mode":"active_document","quality":0.0,"count":0,"error":f"{type(exc).__name__}: {exc}"}
  raw1=self.retrieve_fn(built.text,self.k) or {};e1=self._normalize(raw1);q1=_quality(built.fields.get("current_message"),e1);attempts=([preferred_attempt] if preferred_attempt else [])+[{"mode":"contextual","query":built.to_dict(),"quality":q1,"count":len(e1)}];chosen=(built,raw1,e1,"contextual",q1)
  if current_only is not None and q1<0.5:
   raw2=self.retrieve_fn(current_only.text,self.k) or {};e2=self._normalize(raw2);q2=_quality(current_only.fields.get("current_message"),e2);attempts.append({"mode":"current_turn_only","query":current_only.to_dict(),"quality":q2,"count":len(e2)})
   if q2>q1:chosen=(current_only,raw2,e2,"current_turn_only",q2)
  query,raw,evidence,mode,quality=chosen;expansion={"enabled":False,"reason":"intent_does_not_require_document_expansion","llm_called":False}
  if str(query.fields.get("intent") or "") in {"procedural","requirements"}:limit=18 if str(query.fields.get("intent") or "")=="requirements" else 8;evidence,expansion=_expand_procedure(query.text,evidence,limit)
  groups={}
  for x in evidence:
   identity=_identity(x);g=groups.setdefault(identity,{"identity":identity,"title":x["title"],"pages":[],"chunks":0});g["chunks"]+=1
   if x["page"] and x["page"] not in g["pages"]:g["pages"].append(x["page"])
  return {"enabled":True,"llm_called":False,"production_changed":False,"query":query.to_dict(),"ok":bool(raw.get("ok")),"adapter":raw.get("adapter"),"count":len(evidence),"evidence":evidence,"document_groups":list(groups.values()),"errors":raw.get("errors") or [],"diagnostic_only":True,"selection":{"chosen_mode":mode,"quality":quality,"attempts":attempts,"context_contamination_avoided":mode=="current_turn_only"},"procedural_expansion":expansion}
def retrieval_summary(r):
 if not r.get("ok"):return "No fue posible consultar el índice documental. El error quedó registrado para diagnóstico."
 if not r.get("count"):return "Consulté el índice documental, pero no encontré fragmentos para esta solicitud."
 titles=[]
 for g in r.get("document_groups") or []:
  if g["title"] not in titles:titles.append(g["title"])
 exp=r.get("procedural_expansion") or {};extra=f" Evidencia procedimental ordenada en {len(exp.get('pages') or [])} página(s) del documento principal." if exp.get("attempted") and exp.get("ok") else ""
 return f"Encontré {r['count']} fragmentos en {len(r.get('document_groups') or [])} documento(s). Fuentes principales: "+"; ".join(titles[:3])+"."+extra+" La respuesta documentada procedimental se habilitará después de validar esta evidencia."
