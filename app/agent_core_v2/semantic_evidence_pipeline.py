from __future__ import annotations
from app.agent_core_v2.evidence_judge import SemanticEvidenceJudge,merge_judgment
class SemanticEvidencePipeline:
 def __init__(self,retriever,gateway,max_candidates=6,judge_tokens=260):self.retriever=retriever;self.gateway=gateway;self.max_candidates=max_candidates;self.judge=SemanticEvidenceJudge(gateway,min(280,judge_tokens),max_candidates)
 def _candidates(self,raw,size,start=1):
  out=[];seen=set()
  for index,item in enumerate(raw,1):
   meta=dict(item.get("metadata") or {});key=(str(meta.get("content_hash") or meta.get("canonical_url") or item.get("url") or item.get("title") or index),str(meta.get("page_label") or meta.get("page") or ""))
   if key in seen:continue
   seen.add(key);out.append({"id":f"S{start+len(out)}","title":str(item.get("title") or meta.get("title") or ""),"url":str(item.get("url") or meta.get("source_url") or meta.get("source") or item.get("source") or ""),"text":str(item.get("text") or "")[:2400],"metadata":meta,"retrieval_score":float(item.get("score") or meta.get("score") or .5)})
   if len(out)>=size:break
  return out
 def _judge_initial(self,query,decision,state,candidates):
  judged=self.judge.evaluate(query,decision.intent,decision.entities or state.active_topic.products,candidates)
  amap={str(x.get("id")):x for x in judged.get("assessments") or [] if isinstance(x,dict)}
  assessed=[x for x in candidates if x["id"] in amap]
  result=merge_judgment(assessed,{"assessments":[amap[x["id"]] for x in assessed]}) if assessed else {"retrieved":[],"direct":[],"partial":[],"conditional":[],"contextual":[],"not_applicable":[],"citable":[],"counts":{}}
  return result,judged,amap
 def evaluate(self,query,decision,state,limit=None):
  size=max(3,int(limit or self.max_candidates));initial=self._candidates(list(self.retriever(query,size) or []),size)
  result,judged,amap=self._judge_initial(query,decision,state,initial)
  broad=decision.intent in {"requirements","procedural"};direct=list(result.get("direct") or []);expanded=False;continuation=[]
  # A direct source that declares itself to be the requested requirements/guide
  # is a document lead, not proof that the single chunk is complete.
  if broad and direct:
   lead=direct[0];source=str((lead.get("metadata") or {}).get("canonical_url") or lead.get("url") or "")
   try: raw=list(self.retriever(query,max(8,size),source) or [])
   except TypeError: raw=[]
   continuation=self._candidates(raw,max(8,size),start=len(initial)+1)
   existing={(x.get("url"),str((x.get("metadata") or {}).get("page_label") or (x.get("metadata") or {}).get("page"))) for x in initial}
   continuation=[x for x in continuation if (x.get("url"),str((x.get("metadata") or {}).get("page_label") or (x.get("metadata") or {}).get("page"))) not in existing]
   for item in continuation:
    item["semantic_assessment"]={"applicability":"direct","model_applicability":"direct","subject_match":"same","task_match":"same","scope_relation":"same","reason":"Ordered continuation of the already validated directly applicable document.","conditions":[],"supported_claims":[],"scope_downgraded":False};item["eligible"]=True;item["citable"]=True;item["citation_scope"]="direct"
   if continuation:
    expanded=True;result["retrieved"]=list(result.get("retrieved") or [])+continuation;result["direct"]=list(result.get("direct") or [])+continuation;result["citable"]=list(result.get("citable") or [])+continuation
  missing=[x for x in initial if x["id"] not in amap];result["unassessed"]=missing;result["retrieved"]=list(result.get("retrieved") or [])+missing
  result["judge"]={"ok":bool(amap),"complete":not missing,"assessed":len(amap),"expected":len(initial),"missing_ids":[x["id"] for x in missing],"expanded":expanded,"exact_document_continuation":expanded,"provider_result":judged.get("provider_result")}
  citable=result.get("citable") or [];pages={str((x.get("metadata") or {}).get("page_label") or (x.get("metadata") or {}).get("page")) for x in citable}
  result["answer_completeness"]={"broad_request":broad,"multi_pass_used":expanded,"exact_document_used":expanded,"citable_passages":len(citable),"document_pages":sorted(pages),"complete_enough":bool(direct) and (not broad or len(citable)>=2)}
  return result
 def merge_passes(self,first,second):return second or first
