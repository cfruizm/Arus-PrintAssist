from __future__ import annotations
from app.agent_core_v2.evidence_judge import SemanticEvidenceJudge,merge_judgment

class SemanticEvidencePipeline:
 def __init__(self,retriever,gateway,max_candidates=6,judge_tokens=300):self.retriever=retriever;self.gateway=gateway;self.max_candidates=max_candidates;self.judge=SemanticEvidenceJudge(gateway,judge_tokens,max_candidates)
 def evaluate(self,query,decision,state,limit=None):
  size=int(limit or self.max_candidates);raw=list(self.retriever(query,size) or []);candidates=[];seen=set()
  for index,item in enumerate(raw,1):
   meta=dict(item.get("metadata") or {});key=str(meta.get("content_hash") or item.get("url") or meta.get("source_url") or item.get("title") or index)
   if key in seen:continue
   seen.add(key);candidates.append({"id":f"S{len(candidates)+1}","title":str(item.get("title") or meta.get("title") or ""),"url":str(item.get("url") or meta.get("source_url") or item.get("source") or ""),"text":str(item.get("text") or "")[:1000],"metadata":meta,"retrieval_score":float(item.get("score") or meta.get("score") or .5)})
   if len(candidates)>=size:break
  judged=self.judge.evaluate(query,decision.intent,decision.entities or state.active_topic.products,candidates)
  assessments={str(x.get("id")):x for x in judged.get("assessments") or [] if isinstance(x,dict)} if judged.get("ok") else {}
  missing=[x for x in candidates if x["id"] not in assessments]
  complete=bool(judged.get("ok")) and not missing and len(assessments)==len(candidates)
  if complete:
   result=merge_judgment(candidates,judged);result["unassessed"]=[]
  else:
   assessed_candidates=[x for x in candidates if x["id"] in assessments]
   result=merge_judgment(assessed_candidates,{"assessments":[assessments[x["id"]] for x in assessed_candidates]}) if assessed_candidates else {"retrieved":[],"direct":[],"partial":[],"conditional":[],"contextual":[],"not_applicable":[],"citable":[],"counts":{"retrieved":0,"direct":0,"partial":0,"conditional":0,"contextual":0,"citable":0}}
   unassessed=[]
   for item in missing if judged.get("ok") else candidates:
    copy=dict(item);copy["semantic_assessment"]={"applicability":"unassessed","reason":"La aplicabilidad no pudo verificarse completamente.","supported_claims":[],"conditions":[]};copy["eligible"]=False;copy["citable"]=False;unassessed.append(copy)
   result["retrieved"]=list(result.get("retrieved") or [])+unassessed;result["unassessed"]=unassessed;result.setdefault("counts",{})["retrieved"]=len(candidates);result["counts"]["unassessed"]=len(unassessed)
  result["judge"]={"ok":bool(judged.get("ok")),"complete":complete,"assessed":len(assessments),"expected":len(candidates),"error":judged.get("error"),"provider_result":judged.get("provider_result")};return result
 def merge_passes(self,first,second):return first
