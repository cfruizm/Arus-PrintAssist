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

def warnings_for(data):
 warnings=[]
 if data.get("next_action")=="retrieve" and not data.get("requires_retrieval"):warnings.append("retrieve_action_without_flag")
 if data.get("requires_retrieval") and not data.get("retrieval_request"):warnings.append("retrieval_without_request")
 if data.get("route")=="clarification" and not data.get("requires_clarification"):warnings.append("clarification_route_without_flag")
 if data.get("route")=="escalation" and not data.get("requires_escalation"):warnings.append("escalation_route_without_flag")
 if data.get("route")=="case_update" and any(x.get("type")=="affected_scope" for x in data.get("case_updates",[])) and data.get("intent")!="troubleshooting":warnings.append("impact_update_wrong_intent")
 if data.get("next_action")=="ask_clarification" and data.get("clarification_question") and any(word in data["clarification_question"].lower() for word in ["verificado","reiniciado","espacio disponible","servicio activo","puerto","firewall"]):warnings.append("clarification_suggests_technical_check")
 return warnings

def evaluate_case(gateway,case,max_tokens=220):
 started=time.perf_counter();request=LLMRequest(build_messages(case["message"],case.get("state") or {}),"semantic_orchestrator",max_tokens,0.0,SEMANTIC_DECISION_SCHEMA);result=gateway.complete(request)
 rec={"id":case["id"],"category":case["category"],"message":case["message"],"provider_result":result.to_dict(),"passed":False,"mismatches":[]}
 if not result.ok:return rec
 try:data=validate_semantic_decision(extract_json(result.text)).to_dict()
 except Exception as exc:rec["mismatches"].append(f"invalid_semantic_json:{type(exc).__name__}");return rec
 rec["decision"]=data;rec["consistency_warnings"]=warnings_for(data)
 for key,value in (case.get("expected") or {}).items():
  if key=="update_type":
   actual=[x.get("type") for x in data.get("case_updates",[])]
   if value not in actual:rec["mismatches"].append(f"update_type expected={value} actual={actual}")
  elif data.get(key)!=value:rec["mismatches"].append(f"{key} expected={value} actual={data.get(key)}")
 rec["passed"]=not rec["mismatches"] and not rec["consistency_warnings"];rec["evaluation_latency_ms"]=round((time.perf_counter()-started)*1000,3);return rec

def summarize(records):
 usage={"prompt_tokens":0,"completion_tokens":0,"total_tokens":0};categories={}
 for r in records:
  for k in usage:usage[k]+=int(r.get("provider_result",{}).get("usage",{}).get(k,0) or 0)
  c=r.get("category","unknown");categories.setdefault(c,{"total":0,"passed":0});categories[c]["total"]+=1;categories[c]["passed"]+=int(bool(r.get("passed")))
 return {"total":len(records),"passed":sum(bool(r.get("passed")) for r in records),"failed":sum(not bool(r.get("passed")) for r in records),"usage":usage,"categories":categories,"average_latency_ms":round(sum(float(r.get("provider_result",{}).get("latency_ms",0) or 0) for r in records)/max(1,len(records)),3)}
