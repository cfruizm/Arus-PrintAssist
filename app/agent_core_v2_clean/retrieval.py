from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Callable,Any
import hashlib,json

@dataclass
class RetrievalQuery:
 text:str
 fields:dict[str,Any]
 fingerprint:str
 def to_dict(self):return asdict(self)

class RetrievalQueryBuilder:
 def build(self,message,memory,understanding):
  details={str(k):str(v) for k,v in memory.pending_goal.known_details.items() if str(v).strip()}
  fields={
   "goal":memory.pending_goal.summary or understanding.current_goal,
   "intent":memory.pending_goal.intent or understanding.intent,
   "details":details,
   "symptoms":list(memory.support_case.symptoms),
   "observations":list(memory.support_case.observations[-3:]),
   "affected_scope":memory.support_case.affected_scope,
   "current_message":message,
  }
  parts=[str(fields["goal"] or "").strip()]
  parts.extend(f"{k}: {v}" for k,v in details.items())
  parts.extend(fields["symptoms"])
  if fields["affected_scope"]:parts.append(f"alcance: {fields['affected_scope']}")
  text=". ".join(dict.fromkeys(x for x in parts if x))[:1200]
  fingerprint=hashlib.sha256(json.dumps(fields,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20]
  return RetrievalQuery(text,fields,fingerprint)

class ReadOnlyRetrieval:
 def __init__(self,retrieve_fn:Callable|None=None,k=6):
  self.retrieve_fn=retrieve_fn or self._existing
  self.k=max(1,min(10,int(k)))
 def _existing(self,query,k):
  from app.integration.lab_retrieval_adapter import retrieve_from_existing_backend
  return retrieve_from_existing_backend(query,k)
 def search(self,built:RetrievalQuery):
  raw=self.retrieve_fn(built.text,self.k) or {}
  evidence=[]
  for i,x in enumerate(raw.get("evidence") or [],1):
   meta=dict(x.get("metadata") or {})
   evidence.append({
    "id":f"R{i}","title":str(x.get("title") or meta.get("title") or "Fuente sin título"),
    "source":str(x.get("source") or meta.get("source") or ""),"url":str(x.get("url") or meta.get("source_url") or meta.get("canonical_url") or ""),
    "score":x.get("score"),"page":str(meta.get("page_label") or meta.get("page") or ""),
    "text":str(x.get("text") or "")[:1800],"metadata":meta,
   })
  groups={}
  for x in evidence:
   identity=x["url"] or x["source"] or x["title"]
   g=groups.setdefault(identity,{"identity":identity,"title":x["title"],"pages":[],"chunks":0})
   g["chunks"]+=1
   if x["page"] and x["page"] not in g["pages"]:g["pages"].append(x["page"])
  return {"enabled":True,"llm_called":False,"production_changed":False,"query":built.to_dict(),"ok":bool(raw.get("ok")),"adapter":raw.get("adapter"),"count":len(evidence),"evidence":evidence,"document_groups":list(groups.values()),"errors":raw.get("errors") or [],"diagnostic_only":True}

def retrieval_summary(result):
 if not result.get("ok"):return "No fue posible consultar el índice documental. El error quedó registrado para diagnóstico."
 n=result.get("count",0);docs=len(result.get("document_groups") or [])
 if not n:return "Consulté el índice documental, pero no encontré fragmentos para esta solicitud."
 titles=[]
 for g in result.get("document_groups") or []:
  if g["title"] not in titles:titles.append(g["title"])
 return f"Encontré {n} fragmentos en {docs} documento(s). Fuentes principales: "+"; ".join(titles[:3])+". La respuesta documentada se habilitará después de validar la calidad de esta recuperación."
