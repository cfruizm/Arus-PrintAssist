from __future__ import annotations
from app.agent_core_v2.evidence_judge import SemanticEvidenceJudge,merge_judgment

EMPTY_COUNTS={"retrieved":0,"direct":0,"partial":0,"conditional":0,"contextual":0,"citable":0}

def _empty_result():
 return {"retrieved":[],"direct":[],"partial":[],"conditional":[],"contextual":[],"not_applicable":[],"citable":[],"coverage":{"has_direct_same_scope":False,"has_narrower_sources":False,"all_applicable_sources_narrower":False,"requested_objects":[],"coverage_mode":"none"},"counts":dict(EMPTY_COUNTS),"unassessed":[]}

def _candidate(item,index):
 meta=dict(item.get("metadata") or {})
 return {"id":f"S{index}","title":str(item.get("title") or meta.get("title") or ""),"url":str(item.get("url") or meta.get("source_url") or item.get("source") or ""),"text":str(item.get("text") or "")[:1000],"metadata":meta,"retrieval_score":float(item.get("score") or meta.get("score") or .5)}

def _unassessed(item,reason):
 copy=dict(item);copy["semantic_assessment"]={"id":item["id"],"applicability":"unassessed","model_applicability":"unassessed","subject_match":"unknown","task_match":"unknown","scope_relation":"unknown","requested_object":"unknown","source_object":"unknown","reason":reason,"conditions":[],"supported_claims":[],"scope_downgraded":False};copy["eligible"]=False;copy["citable"]=False;copy["citation_scope"]="none";return copy

class SemanticEvidencePipeline:
 def __init__(self,retriever,gateway,max_candidates=6,judge_tokens=300):self.retriever=retriever;self.gateway=gateway;self.max_candidates=max_candidates;self.judge=SemanticEvidenceJudge(gateway,judge_tokens,max_candidates)
 def evaluate(self,query,decision,state,limit=None):
  size=int(limit or self.max_candidates);raw=list(self.retriever(query,size) or []);candidates=[];seen=set()
  for item in raw:
   meta=dict(item.get("metadata") or {});key=str(meta.get("content_hash") or item.get("url") or meta.get("source_url") or item.get("title") or len(candidates)+1)
   if key in seen:continue
   seen.add(key);candidates.append(_candidate(item,len(candidates)+1))
   if len(candidates)>=size:break
  if not candidates:
   result=_empty_result();result["judge"]={"ok":True,"complete":True,"assessed":0,"expected":0,"missing_ids":[],"error":None,"provider_result":None,"skipped":True,"skip_reason":"no_candidates"};return result
  judged=self.judge.evaluate(query,decision.intent,decision.entities or state.active_topic.products,candidates)
  expected_ids={item["id"] for item in candidates};valid={str(item.get("id")):item for item in judged.get("assessments") or [] if isinstance(item,dict) and str(item.get("id")) in expected_ids};missing_ids=sorted(expected_ids-set(valid));complete=bool(judged.get("ok")) and not missing_ids and len(valid)==len(expected_ids)
  assessed_candidates=[item for item in candidates if item["id"] in valid]
  if assessed_candidates:
   result=merge_judgment(assessed_candidates,{"assessments":[valid[item["id"]] for item in assessed_candidates]})
  else:result=_empty_result()
  reason="La fuente fue recuperada, pero el juez semántico no devolvió una evaluación válida para su identificador."
  unassessed=[_unassessed(item,reason) for item in candidates if item["id"] in missing_ids]
  result["unassessed"]=unassessed;result["retrieved"]=list(result.get("retrieved") or [])+unassessed
  result.setdefault("counts",dict(EMPTY_COUNTS));result["counts"]["retrieved"]=len(candidates);result["counts"]["unassessed"]=len(unassessed)
  result["judge"]={"ok":bool(judged.get("ok")),"complete":complete,"assessed":len(valid),"expected":len(candidates),"missing_ids":missing_ids,"error":judged.get("error") or ("incomplete_assessments" if missing_ids else None),"provider_result":judged.get("provider_result"),"skipped":False}
  return result
 def merge_passes(self,first,second):return first
