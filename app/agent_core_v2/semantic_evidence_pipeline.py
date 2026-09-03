from __future__ import annotations
from app.agent_core_v2.evidence_judge import SemanticEvidenceJudge,merge_judgment
class SemanticEvidencePipeline:
 def __init__(self,retriever,gateway,max_candidates=6,judge_tokens=300):self.retriever=retriever;self.gateway=gateway;self.max_candidates=max(1,min(8,int(max_candidates)));self.judge=SemanticEvidenceJudge(gateway,judge_tokens,self.max_candidates)
 def evaluate(self,query,decision,state,limit=None):
  limit=int(limit or self.max_candidates);raw=list(self.retriever(query,limit) or []);candidates=[];seen=set();expected={e.canonical_id for e in decision.entities if e.kind=="product"}|{e.canonical_id for e in state.active_topic.products}
  for index,d in enumerate(raw,1):
   meta=dict(d.get("metadata") or {});key=str(meta.get("content_hash") or d.get("url") or meta.get("source_url") or d.get("title") or index)
   if key in seen:continue
   seen.add(key);doc_product=str(meta.get("product") or "")
   candidates.append({"id":f"S{len(candidates)+1}","title":str(d.get("title") or meta.get("title") or ""),"url":str(d.get("url") or meta.get("source_url") or d.get("source") or ""),"text":str(d.get("text") or "")[:700],"metadata":meta,"retrieval_score":float(d.get("score") or meta.get("score") or .5),"metadata_product_mismatch":bool(expected and doc_product and doc_product not in expected)})
   if len(candidates)>=limit:break
  result=self.judge.evaluate(query,decision.intent,decision.entities or state.active_topic.products,candidates)
  merged=merge_judgment(candidates,result if result.get("ok") else {"assessments":[]});merged["judge"]={"ok":bool(result.get("ok")),"error":result.get("error"),"provider_result":result.get("provider_result")};return merged
 def merge_passes(self,first,second):
  combined=[];seen=set()
  for source in list(first.get("retrieved") or [])+list(second.get("retrieved") or []):
   key=str((source.get("metadata") or {}).get("content_hash") or source.get("url") or source.get("title"))
   if key in seen:continue
   seen.add(key);copy=dict(source);copy["id"]=f"S{len(combined)+1}";assessment=dict(copy.get("semantic_assessment") or {});assessment["id"]=copy["id"];copy["semantic_assessment"]=assessment;combined.append(copy)
  assessments=[x.get("semantic_assessment") for x in combined];merged=merge_judgment(combined,{"assessments":assessments});merged["judge"]={"ok":bool((first.get("judge") or {}).get("ok")) and bool((second.get("judge") or {}).get("ok")),"passes":2};return merged
