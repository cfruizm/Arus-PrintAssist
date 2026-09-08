from __future__ import annotations
import hashlib,re,unicodedata
from app.agent_core_v2.evidence_judge import SemanticEvidenceJudge,merge_judgment

def _norm(value):
 value=unicodedata.normalize("NFKD",str(value or "")).encode("ascii","ignore").decode().casefold()
 return re.sub(r"[^a-z0-9]+"," ",value).strip()

def _terms(value):
 stop={"que","como","para","por","del","los","las","una","uno","con","segun","the","and","for","from","what","how"}
 return {x for x in _norm(value).split() if len(x)>2 and x not in stop}

class SemanticEvidencePipeline:
 def __init__(self,retriever,gateway,max_candidates=6,judge_tokens=300):
  self.retriever=retriever;self.gateway=gateway;self.max_candidates=max_candidates;self.judge=SemanticEvidenceJudge(gateway,judge_tokens,max_candidates)
 def _identity(self,item):
  m=item.get("metadata") or {};return str(m.get("canonical_url") or m.get("source") or m.get("source_url") or item.get("url") or "")
 def _fingerprint(self,item):
  m=item.get("metadata") or {};raw=str(m.get("content_hash") or "")+"|"+str(item.get("text") or "")
  return hashlib.sha1(raw.encode("utf-8","ignore")).hexdigest()
 def _candidates(self,raw,size,start=1):
  out=[];seen=set()
  for item in raw or []:
   text=str(item.get("text") or "").strip()
   if not text:continue
   key=self._fingerprint(item)
   if key in seen:continue
   seen.add(key);m=dict(item.get("metadata") or {})
   out.append({"id":f"S{start+len(out)}","title":str(item.get("title") or m.get("title") or ""),"url":str(item.get("url") or self._identity(item)),"text":text[:5000],"metadata":m,"retrieval_score":float(item.get("score") or m.get("score") or .5),"chunk_fingerprint":key})
   if len(out)>=size:break
  return out
 def _local_relevance(self,query,decision,item):
  m=item.get("metadata") or {};hay=" ".join([item.get("title", ""),item.get("text", ""),m.get("product", ""),m.get("component", ""),m.get("document_family", "")])
  q=_terms(query);overlap=len(q&_terms(hay))
  entity_ids={_norm(getattr(x,"canonical_id",None) or (x.get("canonical_id") if isinstance(x,dict) else "")) for x in decision.entities or []}
  meta_product=_norm(m.get("product"));subject=bool(meta_product and meta_product in entity_ids) or overlap>=2
  return subject,overlap
 def _is_lead(self,query,decision,item):
  m=item.get("metadata") or {};subject,overlap=self._local_relevance(query,decision,item)
  family=_norm(m.get("document_family"));component=_norm(m.get("component"));total=int(m.get("total_pages") or 0)
  authority=family in {"requirements","guide","procedure","manual","general document"} or component in {"requirements","installation","internal support asset"}
  return total>1 and authority and subject and (decision.intent in {"requirements","procedural","warranty","architecture","troubleshooting"} or overlap>=2)
 def _fallback_assessment(self,query,decision,item):
  subject,overlap=self._local_relevance(query,decision,item)
  if not subject:return None
  # Bounded recovery only preserves the actual excerpt; it does not invent relevance claims.
  return {"id":item["id"],"applicability":"partial","model_applicability":"partial","subject_match":"same","task_match":"same" if overlap>=2 else "related","scope_relation":"same","requested_object":"unknown","source_object":"unknown","reason":"Deterministic recovery from matching metadata and excerpt terms.","conditions":["Semantic judge returned no usable assessment."],"supported_claims":[str(item.get("text") or "")[:700]],"scope_downgraded":True}
 def evaluate(self,query,decision,state,limit=None):
  size=max(3,int(limit or self.max_candidates));initial=self._candidates(self.retriever(query,size),size)
  judged=self.judge.evaluate(query,decision.intent,decision.entities or state.active_topic.products,initial)
  amap={str(x.get("id")):x for x in judged.get("assessments") or [] if isinstance(x,dict)}
  for item in initial:
   if item["id"] not in amap:
    recovered=self._fallback_assessment(query,decision,item)
    if recovered:amap[item["id"]]=recovered
  assessed=[x for x in initial if x["id"] in amap]
  result=merge_judgment(assessed,{"assessments":[amap[x["id"]] for x in assessed]}) if assessed else {"retrieved":[],"direct":[],"partial":[],"conditional":[],"contextual":[],"not_applicable":[],"citable":[],"counts":{},"coverage":{}}
  leads=[x for x in initial if self._is_lead(query,decision,x)];expanded=False;continuation=[]
  if leads:
   lead=leads[0];identity=self._identity(lead)
   try:raw=self.retriever(query,36,identity)
   except TypeError:raw=[]
   exact=self._candidates(raw,36,start=len(initial)+1);existing={self._fingerprint(x) for x in initial}
   continuation=[x for x in exact if self._fingerprint(x) not in existing]
   for item in continuation:
    item["semantic_assessment"]={"applicability":"direct","model_applicability":"direct","subject_match":"same","task_match":"same","scope_relation":"same","requested_object":"document","source_object":"document","reason":"Ordered chunk from an authoritative matched document.","conditions":[],"supported_claims":[item["text"][:900]],"scope_downgraded":False};item["eligible"]=True;item["citable"]=True;item["citation_scope"]="direct"
   if continuation:
    expanded=True
    for key in ("retrieved","direct","citable"):result[key]=list(result.get(key) or [])+continuation
  missing=[x for x in initial if x["id"] not in amap];result["unassessed"]=missing;result["retrieved"]=list(result.get("retrieved") or [])+missing
  citable=result.get("citable") or [];pages=sorted({str((x.get("metadata") or {}).get("page_label") or (x.get("metadata") or {}).get("page")) for x in citable})
  result["judge"]={"ok":bool(amap),"complete":not missing,"assessed":len(amap),"expected":len(initial),"missing_ids":[x["id"] for x in missing],"expanded":expanded,"exact_document_continuation":expanded,"document_lead_ids":[x["id"] for x in leads],"deterministic_recoveries":[x for x in amap if x not in {str(a.get('id')) for a in judged.get('assessments') or []}],"provider_results":judged.get("provider_results") or ([judged.get("provider_result")] if judged.get("provider_result") else [])}
  broad=decision.intent in {"requirements","procedural","warranty"};result["answer_completeness"]={"broad_request":broad,"multi_pass_used":expanded,"exact_document_used":expanded,"same_page_chunks_preserved":expanded,"citable_passages":len(citable),"document_pages":pages,"complete_enough":expanded or bool(result.get("direct"))}
  return result
 def merge_passes(self,first,second):return second or first
