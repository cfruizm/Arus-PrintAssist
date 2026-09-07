from __future__ import annotations
import json
from app.agent_core_v2.evidence_judge import SemanticEvidenceJudge,merge_judgment,_normalized_assessment
EMPTY_COUNTS={"retrieved":0,"direct":0,"partial":0,"conditional":0,"contextual":0,"citable":0,"unassessed":0}
def _empty():return {"retrieved":[],"direct":[],"partial":[],"conditional":[],"contextual":[],"not_applicable":[],"citable":[],"coverage":{"has_direct_same_scope":False,"has_narrower_sources":False,"all_applicable_sources_narrower":False,"requested_objects":[],"coverage_mode":"none"},"counts":dict(EMPTY_COUNTS),"unassessed":[]}
def _candidate(item,index):
 meta=dict(item.get("metadata") or {});return {"id":f"S{index}","title":str(item.get("title") or meta.get("title") or ""),"url":str(item.get("url") or meta.get("source_url") or item.get("source") or ""),"text":str(item.get("text") or "")[:1400],"metadata":meta,"retrieval_score":float(item.get("score") or meta.get("score") or .5)}
def _unassessed(item,reason):
 x=dict(item);x["semantic_assessment"]={"id":item["id"],"applicability":"unassessed","model_applicability":"unassessed","subject_match":"unknown","task_match":"unknown","scope_relation":"unknown","requested_object":"unknown","source_object":"unknown","reason":reason,"conditions":[],"supported_claims":[],"scope_downgraded":False};x["eligible"]=False;x["citable"]=False;x["citation_scope"]="none";return x
def _recover(judged,valid_ids):
 if judged.get("assessments"):return judged
 provider=judged.get("provider_result") or {};text=str(provider.get("text") or "");start=text.find("{");end=text.rfind("}")
 if start<0 or end<start:return judged
 try:raw=json.loads(text[start:end+1])
 except Exception:return judged
 recovered=[]
 for item in raw.get("assessments") or []:
  norm=_normalized_assessment(item,valid_ids)
  if norm:recovered.append(norm)
 if recovered:return {**judged,"ok":True,"assessments":recovered,"error":"partial_recovery","recovery_used":True}
 return judged
class SemanticEvidencePipeline:
 def __init__(self,retriever,gateway,max_candidates=6,judge_tokens=300):self.retriever=retriever;self.gateway=gateway;self.max_candidates=max_candidates;self.judge=SemanticEvidenceJudge(gateway,max(judge_tokens,360),max_candidates)
 def _retrieve(self,query,size):
  raw=list(self.retriever(query,size) or []);out=[];seen=set()
  for item in raw:
   meta=dict(item.get("metadata") or {});key=str(meta.get("content_hash") or item.get("url") or meta.get("source_url") or item.get("title") or len(out))
   if key in seen:continue
   seen.add(key);out.append(_candidate(item,len(out)+1))
  return out
 def evaluate(self,query,decision,state,limit=None):
  initial=max(1,int(limit or min(3,self.max_candidates)));candidates=self._retrieve(query,initial)
  if not candidates:
   r=_empty();r["judge"]={"ok":True,"complete":True,"assessed":0,"expected":0,"missing_ids":[],"error":None,"skipped":True};return r
  judged=self.judge.evaluate(query,decision.intent,decision.entities or state.active_topic.products,candidates);judged=_recover(judged,{x["id"] for x in candidates})
  valid={str(x.get("id")):x for x in judged.get("assessments") or [] if isinstance(x,dict)}
  citable_now=any(x.get("applicability") in {"direct","partial","conditional","contextual"} for x in valid.values())
  expanded=False
  if not citable_now and initial<self.max_candidates:
   larger=self._retrieve(query,self.max_candidates)
   if len(larger)>len(candidates):candidates=larger;expanded=True;judged=_recover(self.judge.evaluate(query,decision.intent,decision.entities or state.active_topic.products,candidates),{x["id"] for x in candidates});valid={str(x.get("id")):x for x in judged.get("assessments") or [] if isinstance(x,dict)}
  expected={x["id"] for x in candidates};valid={k:v for k,v in valid.items() if k in expected};missing=sorted(expected-set(valid));assessed=[x for x in candidates if x["id"] in valid];result=merge_judgment(assessed,{"assessments":[valid[x["id"]] for x in assessed]}) if assessed else _empty();ua=[_unassessed(x,"La fuente fue recuperada, pero no recibió una evaluación semántica válida.") for x in candidates if x["id"] in missing];result["unassessed"]=ua;result["retrieved"]=list(result.get("retrieved") or [])+ua;result.setdefault("counts",dict(EMPTY_COUNTS));result["counts"]["retrieved"]=len(candidates);result["counts"]["unassessed"]=len(ua)
  complete=bool(judged.get("ok")) and not missing;result["judge"]={"ok":bool(judged.get("ok")),"complete":complete,"assessed":len(valid),"expected":len(candidates),"missing_ids":missing,"error":judged.get("error") or ("incomplete_assessments" if missing else None),"provider_result":judged.get("provider_result"),"recovery_used":bool(judged.get("recovery_used")),"expanded":expanded,"skipped":False};return result
 def merge_passes(self,first,second):return first
