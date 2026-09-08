from __future__ import annotations
import hashlib,re,unicodedata
from app.agent_core_v2.evidence_judge import SemanticEvidenceJudge,merge_judgment

def _norm(v):return re.sub(r"[^a-z0-9]+"," ",unicodedata.normalize("NFKD",str(v or "")).encode("ascii","ignore").decode().casefold()).strip()
def _terms(v):
 stop={"que","como","para","por","del","los","las","una","uno","con","segun","the","and","for","from","what","how","sirve","necesita"}
 return {x for x in _norm(v).split() if len(x)>2 and x not in stop}
class SemanticEvidencePipeline:
 def __init__(self,retriever,gateway,max_candidates=6,judge_tokens=300):self.retriever=retriever;self.gateway=gateway;self.max_candidates=max_candidates;self.judge=SemanticEvidenceJudge(gateway,judge_tokens,max_candidates)
 def _identity(self,x):
  m=x.get("metadata") or {};return str(m.get("canonical_url") or m.get("source") or m.get("source_url") or x.get("url") or "")
 def _fp(self,x):return hashlib.sha1((str((x.get("metadata") or {}).get("content_hash") or "")+"|"+str(x.get("text") or "")).encode()).hexdigest()
 def _candidates(self,raw,size,start=1):
  out=[];seen=set()
  for x in raw or []:
   text=str(x.get("text") or "").strip();fp=self._fp(x)
   if not text or fp in seen:continue
   seen.add(fp);m=dict(x.get("metadata") or {});out.append({"id":f"S{start+len(out)}","title":str(x.get("title") or m.get("title") or ""),"url":str(x.get("url") or self._identity(x)),"text":text[:5000],"metadata":m,"retrieval_score":float(x.get("score") if x.get("score") is not None else (m.get("score") if m.get("score") is not None else 0.0)),"chunk_fingerprint":fp})
   if len(out)>=size:break
  return out
 def _entity_match(self,decision,item):
  m=item.get("metadata") or {};want={_norm(getattr(e,"canonical_id",None) or (e.get("canonical_id") if isinstance(e,dict) else "")) for e in decision.entities or []};prod=_norm(m.get("product"))
  return bool(prod and prod in want)
 def _relevance(self,query,decision,item):
  m=item.get("metadata") or {};text=" ".join([item.get("title",""),item.get("text",""),m.get("product",""),m.get("component",""),m.get("document_family","")]);overlap=len(_terms(query)&_terms(text));return overlap+(4 if self._entity_match(decision,item) else 0)
 def _lead(self,query,decision,item):
  m=item.get("metadata") or {};family=_norm(m.get("document_family"));component=_norm(m.get("component"));authority=family in {"requirements","guide","procedure","manual","general document"} or component in {"requirements","installation","internal support asset"}
  return int(m.get("total_pages") or 0)>1 and authority and self._relevance(query,decision,item)>=2
 def _recover(self,query,decision,item):
  score=self._relevance(query,decision,item)
  if score<2:return None
  app="direct" if self._entity_match(decision,item) and score>=5 else "partial"
  return {"id":item["id"],"applicability":app,"model_applicability":app,"subject_match":"same","task_match":"same" if score>=3 else "related","scope_relation":"same","requested_object":"unknown","source_object":"unknown","reason":"Bounded recovery from matching source metadata and excerpt content.","conditions":["Semantic judge returned no usable assessment."],"supported_claims":[str(item.get("text") or "")[:850]],"scope_downgraded":app!="direct"}
 def evaluate(self,query,decision,state,limit=None):
  size=max(3,int(limit or self.max_candidates));initial=self._candidates(self.retriever(query,size),size);judged=self.judge.evaluate(query,decision.intent,decision.entities or state.active_topic.products,initial)
  amap={str(a.get("id")):a for a in judged.get("assessments") or [] if isinstance(a,dict) and a.get("applicability")!="not_applicable"}
  model_ids=set(amap)
  # Missing assessments remain unassessed; lexical or metadata matches never become approved evidence.
  assessed=[x for x in initial if x["id"] in amap];result=merge_judgment(assessed,{"assessments":[amap[x["id"]] for x in assessed]}) if assessed else {"retrieved":[],"direct":[],"partial":[],"conditional":[],"contextual":[],"not_applicable":[],"citable":[],"counts":{},"coverage":{}}
  leads=[x for x in initial if self._lead(query,decision,x)];expanded=False
  if leads:
   identity=self._identity(max(leads,key=lambda x:self._relevance(query,decision,x)))
   try:raw=self.retriever(query,40,identity)
   except TypeError:raw=[]
   existing={self._fp(x) for x in initial};cont=[x for x in self._candidates(raw,40,start=len(initial)+1) if self._fp(x) not in existing]
   for x in cont:
    score=self._relevance(query,decision,x);x["query_relevance_score"]=score;x["semantic_assessment"]={"applicability":"contextual","model_applicability":"contextual","subject_match":"same","task_match":"unknown","scope_relation":"unknown","requested_object":"document","source_object":"document","reason":"Preserved for later semantic assessment.","conditions":[],"supported_claims":[],"scope_downgraded":True};x["eligible"]=False;x["citable"]=False;x["citation_scope"]="none"
   if cont:
    expanded=True
    result["retrieved"]=list(result.get("retrieved") or [])+cont
    result["unassessed"]=list(result.get("unassessed") or [])+cont
  missing=[x for x in initial if x["id"] not in amap];result["unassessed"]=missing;result["retrieved"]=list(result.get("retrieved") or [])+missing
  c=result.get("citable") or [];pages=sorted({str((x.get("metadata") or {}).get("page_label") or (x.get("metadata") or {}).get("page")) for x in c})
  specific=decision.intent in {"conceptual"} or len(_terms(query))<=7
  result["judge"]={"ok":bool(amap),"complete":not missing,"assessed":len(amap),"expected":len(initial),"missing_ids":[x["id"] for x in missing],"expanded":expanded,"exact_document_continuation":expanded,"document_lead_ids":[x["id"] for x in leads],"deterministic_recoveries":[],"provider_results":judged.get("provider_results") or ([judged.get("provider_result")] if judged.get("provider_result") else [])}
  result["answer_completeness"]={"broad_request":not specific,"request_scope":"specific" if specific else "broad","multi_pass_used":expanded,"exact_document_used":expanded,"same_page_chunks_preserved":expanded,"citable_passages":len(c),"document_pages":pages,"complete_enough":expanded or bool(result.get("direct"))}
  return result
 def merge_passes(self,first,second):return second or first


