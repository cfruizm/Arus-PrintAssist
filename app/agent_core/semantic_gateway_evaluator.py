from __future__ import annotations
import json,re,time
from app.agent_core.semantic_gateway_prompt import build_messages
from app.agent_core.semantic_gateway_schema import SEMANTIC_DECISION_SCHEMA
from app.agent_core.semantic_schema import validate_semantic_decision
from app.llm_gateway.models import LLMRequest

def extract_json(text):
 value=str(text or "").strip()
 if value.startswith("```"):value=re.sub(r"^```(?:json)?\s*|\s*```$","",value,flags=re.I|re.S).strip()
 try:return json.loads(value)
 except Exception:
  match=re.search(r"\{.*\}",value,re.S)
  if not match:raise ValueError("model_output_not_json")
  return json.loads(match.group(0))

def consistency_warnings(data):
 warnings=[]
 if data.get("next_action")=="retrieve" and not data.get("requires_retrieval"):warnings.append("retrieve_action_without_flag")
 if data.get("requires_retrieval") and not data.get("retrieval_request"):warnings.append("retrieval_without_request")
 if data.get("route")=="clarification" and not data.get("requires_clarification"):warnings.append("clarification_route_without_flag")
 if data.get("route")=="escalation" and not data.get("requires_escalation"):warnings.append("escalation_route_without_flag")
 return warnings

def evaluate_case(gateway,case,max_tokens=180):
 started=time.perf_counter();messages=build_messages(case["message"],case.get("state") or {})
 request=LLMRequest(messages,"semantic_orchestrator",max_tokens,0.0,SEMANTIC_DECISION_SCHEMA)
 result=gateway.complete(request)
 record={"id":case.get("id"),"category":case.get("category"),"message":case["message"],"state":case.get("state") or {},"provider_result":result.to_dict(),"passed":False,"mismatches":[]}
 if not result.ok:return record
 try:data=validate_semantic_decision(extract_json(result.text)).to_dict()
 except Exception as exc:record["mismatches"].append(f"invalid_semantic_json:{type(exc).__name__}");return record
 record["decision"]=data;record["consistency_warnings"]=consistency_warnings(data)
 expected=case.get("expected") or {}
 for key,value in expected.items():
  if key=="update_type":
   actual=[item.get("type") for item in data.get("case_updates") or []]
   if value not in actual:record["mismatches"].append(f"update_type expected={value} actual={actual}")
  elif data.get(key)!=value:record["mismatches"].append(f"{key} expected={value} actual={data.get(key)}")
 record["passed"]=not record["mismatches"] and not record["consistency_warnings"]
 record["evaluation_latency_ms"]=round((time.perf_counter()-started)*1000,3)
 return record

def summarize(records):
 valid=[r for r in records if r.get("provider_result",{}).get("ok")];usage={"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}
 for r in records:
  for k in usage:usage[k]+=int(r.get("provider_result",{}).get("usage",{}).get(k,0) or 0)
 return {"total":len(records),"provider_success":len(valid),"passed":sum(bool(r.get("passed")) for r in records),"failed":sum(not bool(r.get("passed")) for r in records),"usage":usage,"average_latency_ms":round(sum(float(r.get("provider_result",{}).get("latency_ms",0) or 0) for r in records)/max(1,len(records)),3)}
