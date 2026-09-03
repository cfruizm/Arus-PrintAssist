from __future__ import annotations
from app.agent_core_v2.evidence_judge import SemanticEvidenceJudge,merge_judgment

class SemanticEvidencePipeline:
 def __init__(self,retriever,gateway,max_candidates=6,judge_tokens=360):self.retriever=retriever;self.gateway=gateway;self.max_candidates=max_candidates;self.judge=SemanticEvidenceJudge(gateway,judge_tokens,max_candidates)
 def evaluate(self,query,decision,state,limit=8):
  raw=list(self.retriever(query,limit) or []);candidates=[];seen=set();expected={e.canonical_id for e in decision.entities if e.kind=="product"}|{e.canonical_id for e in state.active_topic.products}
  for index,d in enumerate(raw,1):
   meta=dict(d.get("metadata") or {});key=str(meta.get("content_hash") or d.get("url") or meta.get("source_url") or d.get("title") or index)
   if key in seen:continue
   seen.add(key);doc_product=str(meta.get("product") or "");clear_mismatch=bool(expected and doc_product and doc_product not in expected)
   # Keep metadata mismatches as candidates because the judge can recognize multi-edition documents from title/excerpt.
   candidates.append({"id":f"S{len(candidates)+1}","title":str(d.get("title") or meta.get("title") or ""),"url":str(d.get("url") or meta.get("source_url") or d.get("source") or ""),"text":str(d.get("text") or ""),"metadata":meta,"retrieval_score":float(d.get("score") or meta.get("score") or .5),"metadata_product_mismatch":clear_mismatch})
   if len(candidates)>=self.max_candidates:break
  result=self.judge.evaluate(query,decision.intent,decision.entities or state.active_topic.products,candidates)
  if not result.get("ok"):
   safe=merge_judgment(candidates,{"assessments":[]});safe["judge"]={"ok":False,"error":result.get("error"),"provider_result":result.get("provider_result")};return safe
  merged=merge_judgment(candidates,result);merged["judge"]={"ok":True,"provider_result":result.get("provider_result")};return merged
