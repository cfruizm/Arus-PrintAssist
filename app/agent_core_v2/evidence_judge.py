from __future__ import annotations
import json
ALLOWED={"direct","partial","conditional","contextual","not_applicable"};RELATIONS={"same","narrower","broader","conditional","unknown","different"};OBJECTS={"product","component","operation","incident","feature","unknown"}
def _extract(text):
 text=str(text or "").strip();a=text.find("{");b=text.rfind("}")
 if a<0 or b<a:raise ValueError("judge_incomplete_json")
 return json.loads(text[a:b+1])
def _clip(v,n):return " ".join(str(v or "").split())[:n]
class SemanticEvidenceJudge:
 def __init__(self,gateway,max_tokens=300,max_candidates=6):self.gateway=gateway;self.max_tokens=max(260,min(440,int(max_tokens)));self.max_candidates=max(1,min(8,int(max_candidates)))
 def evaluate(self,query,intent,entities,candidates):
  from app.llm_gateway.models import LLMRequest
  selected=list(candidates or [])[:self.max_candidates];valid_ids={str(x.get("id")) for x in selected};payload={"request":{"text":query,"intent":intent,"entities":[{"kind":getattr(x,"kind",None) or (x.get("kind") if isinstance(x,dict) else None),"name":getattr(x,"canonical_name",None) or (x.get("canonical_name") if isinstance(x,dict) else None)} for x in entities]},"candidates":[{"id":x.get("id"),"title":_clip(x.get("title"),180),"metadata":x.get("metadata") or {},"excerpt":_clip(x.get("text"),700)} for x in selected]}
  system="""Judge semantic evidence applicability and SCOPE. Infer the requested object and source object independently. direct requires same subject, task and scope. If a source addresses only a module, feature, component or operation while the request asks about the whole product, scope_relation is narrower and applicability cannot be direct. partial means useful but incomplete or narrower. conditional requires an explicit condition. contextual is background only. not_applicable is unrelated. For troubleshooting, a feature-specific procedure is not direct unless the incident concerns that feature. Return JSON only and never invent beyond excerpts."""
  schema={"type":"object","properties":{"assessments":{"type":"array","items":{"type":"object"}}},"required":["assessments"]};r=self.gateway.complete(LLMRequest([{"role":"system","content":system},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"),default=str)}],"agent_core_v2_evidence_judge",self.max_tokens,0.,schema))
  if not r.ok or r.finish_reason=="length":return {"ok":False,"error":"judge_failed_or_truncated","assessments":[],"provider_result":r.to_dict()}
  try:raw=_extract(r.text)
  except Exception:return {"ok":False,"error":"judge_invalid_json","assessments":[],"provider_result":r.to_dict()}
  out=[];seen=set()
  for item in raw.get("assessments") or []:
   if not isinstance(item,dict):continue
   sid=str(item.get("id") or "");app=str(item.get("applicability") or "not_applicable");scope=str(item.get("scope_relation") or "unknown");requested=str(item.get("requested_object") or "unknown");source=str(item.get("source_object") or "unknown")
   if sid not in valid_ids or sid in seen:continue
   seen.add(sid)
   if app not in ALLOWED:app="not_applicable"
   if scope not in RELATIONS:scope="unknown"
   if requested not in OBJECTS:requested="unknown"
   if source not in OBJECTS:source="unknown"
   original=app
   if scope=="different":app="not_applicable"
   elif app=="direct" and scope in {"narrower","broader","conditional","unknown"}:app="partial" if scope!="conditional" else "conditional"
   out.append({"id":sid,"applicability":app,"model_applicability":original,"subject_match":str(item.get("subject_match") or "unknown"),"task_match":str(item.get("task_match") or "unknown"),"scope_relation":scope,"requested_object":requested,"source_object":source,"reason":_clip(item.get("reason"),220),"conditions":[_clip(x,130) for x in (item.get("conditions") or [])[:3]],"supported_claims":[_clip(x,180) for x in (item.get("supported_claims") or [])[:4]],"scope_downgraded":app!=original})
  for sid in valid_ids-seen:out.append({"id":sid,"applicability":"not_applicable","model_applicability":"missing","subject_match":"unknown","task_match":"unknown","scope_relation":"unknown","requested_object":"unknown","source_object":"unknown","reason":"No valid assessment returned.","conditions":[],"supported_claims":[],"scope_downgraded":False})
  return {"ok":True,"assessments":out,"provider_result":r.to_dict()}
def merge_judgment(candidates,result):
 mapping={x["id"]:x for x in result.get("assessments") or []};merged=[]
 for source in candidates or []:
  item=dict(source);a=mapping.get(str(source.get("id"))) or {"applicability":"not_applicable","reason":"Judge unavailable.","conditions":[],"supported_claims":[],"scope_relation":"unknown"};item["semantic_assessment"]=a;app=a["applicability"];item["citable"]=app in {"direct","partial","conditional"};item["eligible"]=app!="not_applicable";item["citation_scope"]="direct" if app=="direct" else "qualified" if item["citable"] else "none";merged.append(item)
 return {"retrieved":merged,"direct":[x for x in merged if x["semantic_assessment"]["applicability"]=="direct"],"partial":[x for x in merged if x["semantic_assessment"]["applicability"]=="partial"],"conditional":[x for x in merged if x["semantic_assessment"]["applicability"]=="conditional"],"contextual":[x for x in merged if x["semantic_assessment"]["applicability"]=="contextual"],"citable":[x for x in merged if x["citable"]],"counts":{"retrieved":len(merged),"direct":sum(x["semantic_assessment"]["applicability"]=="direct" for x in merged),"partial":sum(x["semantic_assessment"]["applicability"]=="partial" for x in merged),"conditional":sum(x["semantic_assessment"]["applicability"]=="conditional" for x in merged),"contextual":sum(x["semantic_assessment"]["applicability"]=="contextual" for x in merged),"citable":sum(x["citable"] for x in merged)}}
