from __future__ import annotations
from app.agent_core_v2.evidence_judge import SemanticEvidenceJudge,merge_judgment
class SemanticEvidencePipeline:
 def __init__(self,retriever,gateway,max_candidates=6,judge_tokens=360):self.retriever=retriever;self.gateway=gateway;self.max_candidates=max_candidates;self.judge=SemanticEvidenceJudge(gateway,judge_tokens,max_candidates)
 def _candidates(self,raw,size,start=1):
  out=[];seen=set()
  for index,item in enumerate(raw,1):
   meta=dict(item.get("metadata") or {});key=(str(meta.get("content_hash") or meta.get("canonical_url") or item.get("url") or item.get("title") or index),str(meta.get("page_label") or meta.get("page") or ""))
   if key in seen:continue
   seen.add(key);out.append({"id":f"S{start+len(out)}","title":str(item.get("title") or meta.get("title") or ""),"url":str(item.get("url") or meta.get("source_url") or meta.get("source") or item.get("source") or ""),"text":str(item.get("text") or "")[:1800],"metadata":meta,"retrieval_score":float(item.get("score") or meta.get("score") or .5)})
   if len(out)>=size:break
  return out
 def _judge_all(self,query,intent,entities,candidates):
  assessments=[];provider=[]
  for i in range(0,len(candidates),2):
   r=self.judge.evaluate(query,intent,entities,candidates[i:i+2]);provider.append(r.get("provider_result"));assessments.extend(r.get("assessments") or [])
  return assessments,provider
 def evaluate(self,query,decision,state,limit=None):
  size=max(3,int(limit or self.max_candidates));candidates=self._candidates(list(self.retriever(query,size) or []),size)
  entities=decision.entities or state.active_topic.products;assessments,providers=self._judge_all(query,decision.intent,entities,candidates)
  amap={str(x.get("id")):x for x in assessments if isinstance(x,dict)};missing=[x for x in candidates if x["id"] not in amap]
  # One completeness-focused pass. Prefer more passages from the strongest document, but do not hard filter.
  initial=merge_judgment([x for x in candidates if x["id"] in amap],{"assessments":[amap[x["id"]] for x in candidates if x["id"] in amap]}) if amap else {"retrieved":[],"direct":[],"partial":[],"conditional":[],"contextual":[],"not_applicable":[],"citable":[],"counts":{}}
  broad=decision.intent in {"requirements","procedural"};expanded=False
  if broad and (not initial.get("direct") or len(initial.get("citable") or [])<2):
   strongest=(initial.get("citable") or candidates)[:1];doc=strongest[0].get("metadata",{}) if strongest else {};title=strongest[0].get("title","") if strongest else ""
   focus=f"{query}. Recuperar información complementaria y completa, incluyendo todos los pasos, requisitos, condiciones, excepciones y validaciones disponibles. Priorizar otros fragmentos del documento: {title}."
   extra=self._candidates(list(self.retriever(focus,size+2) or []),size+2,start=len(candidates)+1)
   existing={(x['url'],str(x.get('metadata',{}).get('page_label') or x.get('metadata',{}).get('page'))) for x in candidates}
   extra=[x for x in extra if (x['url'],str(x.get('metadata',{}).get('page_label') or x.get('metadata',{}).get('page'))) not in existing]
   if extra:
    ea,ep=self._judge_all(query,decision.intent,entities,extra);providers.extend(ep);assessments.extend(ea);candidates.extend(extra);expanded=True
  amap={str(x.get("id")):x for x in assessments if isinstance(x,dict)};assessed=[x for x in candidates if x["id"] in amap]
  result=merge_judgment(assessed,{"assessments":[amap[x["id"]] for x in assessed]}) if assessed else {"retrieved":[],"direct":[],"partial":[],"conditional":[],"contextual":[],"not_applicable":[],"citable":[],"counts":{}}
  missing=[x for x in candidates if x["id"] not in amap];result["unassessed"]=missing;result["retrieved"]=list(result.get("retrieved") or [])+missing
  result["judge"]={"ok":bool(amap),"complete":not missing,"assessed":len(amap),"expected":len(candidates),"missing_ids":[x["id"] for x in missing],"expanded":expanded,"batched":True,"provider_results":providers}
  result["answer_completeness"]={"broad_request":broad,"multi_pass_used":expanded,"citable_passages":len(result.get("citable") or []),"complete_enough":bool(result.get("direct")) and (not broad or len(result.get("citable") or [])>=2)}
  return result
 def merge_passes(self,first,second):return second or first
