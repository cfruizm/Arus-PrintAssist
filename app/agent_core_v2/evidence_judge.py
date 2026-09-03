from __future__ import annotations
import json,re
from typing import Any

ALLOWED={"direct","partial","conditional","contextual","not_applicable"}
JUDGE_SCHEMA={"type":"object","properties":{"assessments":{"type":"array","items":{"type":"object","properties":{"id":{"type":"string"},"applicability":{"type":"string","enum":sorted(ALLOWED)},"reason":{"type":"string"},"conditions":{"type":"array","items":{"type":"string"}},"supported_claims":{"type":"array","items":{"type":"string"}}},"required":["id","applicability","reason","conditions","supported_claims"]}}},"required":["assessments"]}

def _json(text):
 text=str(text or "").strip();a=text.find("{");b=text.rfind("}")
 if a<0 or b<a:raise ValueError("evidence_judge_incomplete_json")
 return json.loads(text[a:b+1])
def _clip(v,n=900):return " ".join(str(v or "").split())[:n]
def _safe_id(v):return str(v or "").strip()

class SemanticEvidenceJudge:
 def __init__(self,gateway,max_tokens=360,max_candidates=6):self.gateway=gateway;self.max_tokens=max(260,min(420,int(max_tokens)));self.max_candidates=max(1,min(8,int(max_candidates)))
 def evaluate(self,query,intent,entities,candidates):
  from app.llm_gateway.models import LLMRequest
  selected=list(candidates or [])[:self.max_candidates];ids={_safe_id(x.get("id")) for x in selected}
  payload={"query":query,"intent":intent,"entities":[{"kind":getattr(x,"kind",None) or x.get("kind"),"id":getattr(x,"canonical_id",None) or x.get("canonical_id"),"name":getattr(x,"canonical_name",None) or x.get("canonical_name")} for x in entities],"candidates":[{"id":x.get("id"),"title":_clip(x.get("title"),180),"document_product":(x.get("metadata") or {}).get("product"),"document_family":(x.get("metadata") or {}).get("document_family"),"excerpt":_clip(x.get("text"),900)} for x in selected]}
  system="""Judge evidence applicability for a printing-support query. Evaluate meaning across languages, not just word overlap. direct means the excerpt directly supports the requested answer. partial means it supports a useful subset. conditional means it applies only if an explicit condition is true. contextual means background only. not_applicable means it should not influence the answer. For procedural requests, direct evidence must support the requested operation itself; generic troubleshooting, requirements, installation planning, or secure-release descriptions are not direct procedures. For troubleshooting, an article explicitly naming the symptom and product editions can be direct even when metadata names only one related edition. Return compact JSON only. Never invent facts beyond excerpts."""
  r=self.gateway.complete(LLMRequest([{"role":"system","content":system},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"),default=str)}],"agent_core_v2_evidence_judge",self.max_tokens,0.,JUDGE_SCHEMA))
  if not r.ok:return {"ok":False,"error":r.error_message or "judge_provider_error","assessments":[],"provider_result":r.to_dict()}
  if r.finish_reason=="length":return {"ok":False,"error":"judge_truncated","assessments":[],"provider_result":r.to_dict()}
  raw=_json(r.text);out=[];seen=set()
  for item in raw.get("assessments") or []:
   if not isinstance(item,dict):continue
   sid=_safe_id(item.get("id"));app=str(item.get("applicability") or "")
   if sid not in ids or sid in seen or app not in ALLOWED:continue
   seen.add(sid);out.append({"id":sid,"applicability":app,"reason":_clip(item.get("reason"),180),"conditions":[_clip(x,120) for x in (item.get("conditions") or [])[:3]],"supported_claims":[_clip(x,180) for x in (item.get("supported_claims") or [])[:4]]})
  # Missing assessments fail closed.
  for sid in ids-seen:out.append({"id":sid,"applicability":"not_applicable","reason":"No valid assessment returned.","conditions":[],"supported_claims":[]})
  return {"ok":True,"assessments":out,"provider_result":r.to_dict()}

def merge_judgment(candidates,result):
 mapping={x["id"]:x for x in (result.get("assessments") or [])};merged=[]
 for source in candidates or []:
  item=dict(source);assessment=mapping.get(str(source.get("id"))) or {"applicability":"not_applicable","reason":"Semantic judge unavailable.","conditions":[],"supported_claims":[]}
  item["semantic_assessment"]=assessment;app=assessment["applicability"]
  item["citable"]=app in {"direct","partial","conditional"}
  item["eligible"]=app!="not_applicable"
  item["citation_scope"]="direct" if app=="direct" else "qualified" if app in {"partial","conditional"} else "none"
  merged.append(item)
 return {"retrieved":merged,"direct":[x for x in merged if x["semantic_assessment"]["applicability"]=="direct"],"partial":[x for x in merged if x["semantic_assessment"]["applicability"]=="partial"],"conditional":[x for x in merged if x["semantic_assessment"]["applicability"]=="conditional"],"contextual":[x for x in merged if x["semantic_assessment"]["applicability"]=="contextual"],"citable":[x for x in merged if x["citable"]],"counts":{"retrieved":len(merged),"direct":sum(x["semantic_assessment"]["applicability"]=="direct" for x in merged),"partial":sum(x["semantic_assessment"]["applicability"]=="partial" for x in merged),"conditional":sum(x["semantic_assessment"]["applicability"]=="conditional" for x in merged),"contextual":sum(x["semantic_assessment"]["applicability"]=="contextual" for x in merged),"citable":sum(bool(x["citable"]) for x in merged)}}
