from __future__ import annotations
from app.agent_core_v2.evidence_judge import SemanticEvidenceJudge,merge_judgment

class SemanticEvidencePipeline:
 def __init__(self,retriever,gateway,max_candidates=6,judge_tokens=300):
  self.retriever=retriever;self.gateway=gateway;self.max_candidates=max_candidates
  self.judge=SemanticEvidenceJudge(gateway,judge_tokens,max_candidates)

 def _candidates(self,raw,size,start=1):
  out=[];seen=set()
  for item in raw or []:
   meta=dict(item.get("metadata") or {})
   page=str(meta.get("page_label") or meta.get("page") or "")
   source=str(meta.get("canonical_url") or meta.get("source") or item.get("url") or item.get("title") or "")
   key=(source,page)
   if key in seen or not str(item.get("text") or "").strip():continue
   seen.add(key)
   out.append({"id":f"S{start+len(out)}","title":str(item.get("title") or meta.get("title") or ""),"url":str(item.get("url") or source),"text":str(item.get("text") or "")[:4000],"metadata":meta,"retrieval_score":float(item.get("score") or meta.get("score") or .5)})
   if len(out)>=size:break
  return out

 def _source_identity(self,item):
  meta=item.get("metadata") or {}
  return str(meta.get("canonical_url") or meta.get("source") or item.get("url") or "")

 def _is_document_lead(self,item,decision):
  """Recognize an authoritative document before judging chunk completeness.

  Applicability describes the current excerpt. It must not prevent opening the
  rest of a document whose identity and declared purpose match the request.
  """
  a=item.get("semantic_assessment") or {};meta=item.get("metadata") or {}
  if a.get("subject_match")!="same" or a.get("task_match") not in {"same","related"}:return False
  if a.get("applicability")=="not_applicable":return False
  family=str(meta.get("document_family") or "").casefold();component=str(meta.get("component") or "").casefold()
  total=int(meta.get("total_pages") or 0)
  authoritative=family in {"requirements","guide","procedure","manual","general_document"} or component in {"requirements","installation","internal_support_asset"}
  return authoritative and total>1 and decision.intent in {"requirements","procedural","warranty","architecture","troubleshooting"}

 def evaluate(self,query,decision,state,limit=None):
  size=max(3,int(limit or self.max_candidates));initial=self._candidates(self.retriever(query,size),size)
  judged=self.judge.evaluate(query,decision.intent,decision.entities or state.active_topic.products,initial)
  assessments={str(x.get("id")):x for x in judged.get("assessments") or [] if isinstance(x,dict)}
  assessed=[x for x in initial if x["id"] in assessments]
  result=merge_judgment(assessed,{"assessments":[assessments[x["id"]] for x in assessed]}) if assessed else {"retrieved":[],"direct":[],"partial":[],"conditional":[],"contextual":[],"not_applicable":[],"citable":[],"counts":{},"coverage":{}}
  for item in result.get("retrieved") or []:
   original=next((x for x in initial if x["id"]==item["id"]),None)
   if original:original.update(item)
  broad=decision.intent in {"requirements","procedural","warranty"}
  leads=[x for x in initial if self._is_document_lead(x,decision)]
  expanded=False;continuation=[]
  if leads:
   lead=leads[0];identity=self._source_identity(lead)
   try:raw=self.retriever(query,max(10,size),identity)
   except TypeError:raw=[]
   continuation=self._candidates(raw,max(10,size),start=len(initial)+1)
   existing={(self._source_identity(x),str((x.get("metadata") or {}).get("page_label") or (x.get("metadata") or {}).get("page"))) for x in initial}
   continuation=[x for x in continuation if (self._source_identity(x),str((x.get("metadata") or {}).get("page_label") or (x.get("metadata") or {}).get("page"))) not in existing]
   for item in continuation:
    item["semantic_assessment"]={"applicability":"direct","model_applicability":"direct","subject_match":"same","task_match":"same","scope_relation":"same","requested_object":"document","source_object":"document","reason":"Ordered continuation of an authoritative source already matched to the request.","conditions":[],"supported_claims":[item["text"]],"scope_downgraded":False}
    item["eligible"]=True;item["citable"]=True;item["citation_scope"]="direct"
   if continuation:
    expanded=True
    result["retrieved"]=list(result.get("retrieved") or [])+continuation
    result["direct"]=list(result.get("direct") or [])+continuation
    result["citable"]=list(result.get("citable") or [])+continuation
  missing=[x for x in initial if x["id"] not in assessments]
  result["unassessed"]=missing;result["retrieved"]=list(result.get("retrieved") or [])+missing
  result["judge"]={"ok":bool(assessments),"complete":not missing,"assessed":len(assessments),"expected":len(initial),"missing_ids":[x["id"] for x in missing],"expanded":expanded,"exact_document_continuation":expanded,"document_lead_ids":[x["id"] for x in leads],"provider_results":judged.get("provider_results") or ([judged.get("provider_result")] if judged.get("provider_result") else [])}
  citable=result.get("citable") or [];pages=sorted({str((x.get("metadata") or {}).get("page_label") or (x.get("metadata") or {}).get("page")) for x in citable})
  result["answer_completeness"]={"broad_request":broad,"multi_pass_used":expanded,"exact_document_used":expanded,"citable_passages":len(citable),"document_pages":pages,"complete_enough":expanded or bool(result.get("direct"))}
  return result

 def merge_passes(self,first,second):return second or first
