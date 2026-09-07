from __future__ import annotations
from app.agent_core_v2.evidence_judge import SemanticEvidenceJudge,merge_judgment
class SemanticEvidencePipeline:
 def __init__(self,retriever,gateway,max_candidates=6,judge_tokens=300):self.retriever=retriever;self.gateway=gateway;self.max_candidates=max_candidates;self.judge=SemanticEvidenceJudge(gateway,judge_tokens,max_candidates)
 def evaluate(self,query,decision,state,limit=None):
  limit=int(limit or self.max_candidates);raw=list(self.retriever(query,limit) or []);candidates=[];seen=set()
  for index,item in enumerate(raw,1):
   meta=dict(item.get("metadata") or {});key=str(meta.get("content_hash") or item.get("url") or meta.get("source_url") or item.get("title") or index)
   if key in seen:continue
   seen.add(key);candidates.append({"id":f"S{len(candidates)+1}","title":str(item.get("title") or meta.get("title") or ""),"url":str(item.get("url") or meta.get("source_url") or item.get("source") or ""),"text":str(item.get("text") or "")[:900],"metadata":meta,"retrieval_score":float(item.get("score") or meta.get("score") or .5)})
   if len(candidates)>=limit:break
  judged=self.judge.evaluate(query,decision.intent,decision.entities or state.active_topic.products,candidates)
  if judged.get("ok"):
   result=merge_judgment(candidates,judged);result["unassessed"]=[]
  else:
   unassessed=[]
   for item in candidates:
    copy=dict(item);copy["semantic_assessment"]={"applicability":"unassessed","reason":"La aplicabilidad no pudo evaluarse por un fallo técnico del juez.","supported_claims":[],"conditions":[]};copy["eligible"]=False;copy["citable"]=False;unassessed.append(copy)
   result={"retrieved":unassessed,"direct":[],"partial":[],"conditional":[],"contextual":[],"not_applicable":[],"unassessed":unassessed,"citable":[],"counts":{"retrieved":len(unassessed),"direct":0,"partial":0,"conditional":0,"contextual":0,"unassessed":len(unassessed),"citable":0}}
  result["judge"]={"ok":bool(judged.get("ok")),"error":judged.get("error"),"provider_result":judged.get("provider_result")};return result
 def merge_passes(self,first,second):return first
