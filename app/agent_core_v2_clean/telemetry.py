from copy import deepcopy
def empty():return {"schema_version":3,"calls":0,"provider_failed_calls":0,"contract_failed_calls":0,"functional_failed_calls":0,"prompt_tokens":0,"completion_tokens":0,"total_tokens":0,"latency_ms":0.0,"by_purpose":{},"last_rate_limit":None}
def normalize(raw=None):
 src=dict(raw or {});out=empty()
 for key in ("calls","prompt_tokens","completion_tokens","total_tokens"):out[key]=int(src.get(key) or 0)
 out["latency_ms"]=float(src.get("latency_ms") or 0);legacy=int(src.get("failed_calls") or 0);out["provider_failed_calls"]=int(src.get("provider_failed_calls",legacy) or 0);out["contract_failed_calls"]=int(src.get("contract_failed_calls") or 0);out["functional_failed_calls"]=int(src.get("functional_failed_calls") or 0);out["last_rate_limit"]=src.get("last_rate_limit")
 for purpose,data in (src.get("by_purpose") or {}).items():
  d=dict(data or {});lf=int(d.get("failed_calls") or 0);out["by_purpose"][purpose]={"calls":int(d.get("calls") or 0),"provider_failed_calls":int(d.get("provider_failed_calls",lf) or 0),"contract_failed_calls":int(d.get("contract_failed_calls") or 0),"prompt_tokens":int(d.get("prompt_tokens") or 0),"completion_tokens":int(d.get("completion_tokens") or 0),"total_tokens":int(d.get("total_tokens") or 0),"latency_ms":float(d.get("latency_ms") or 0)}
 return out
def add_result(t,result,contract_valid=None):
 if not result or result.get("skipped"):return
 purpose=str(result.get("purpose") or (result.get("metadata") or {}).get("attempted_purpose") or "unknown");usage=result.get("usage") or {};b=t["by_purpose"].setdefault(purpose,{"calls":0,"provider_failed_calls":0,"contract_failed_calls":0,"prompt_tokens":0,"completion_tokens":0,"total_tokens":0,"latency_ms":0.0});provider_ok=bool(result.get("ok"));contract_evaluated=contract_valid is not None;contract_ok=True if not contract_evaluated else bool(contract_valid)
 for target in (t,b):
  target["calls"]+=1;target["provider_failed_calls"]+=0 if provider_ok else 1;target["contract_failed_calls"]+=0 if contract_ok else 1;target["latency_ms"]+=float(result.get("latency_ms") or 0)
  for k in ("prompt_tokens","completion_tokens","total_tokens"):target[k]+=int(usage.get(k) or 0)
 # Provider availability failures are not contract or functional failures.
 if provider_ok and contract_evaluated and not contract_ok:t["functional_failed_calls"]+=1
 md=result.get("metadata") or {}
 if result.get("error_code")=="rate_limited" or md.get("provider_error_code")=="rate_limit_exceeded":t["last_rate_limit"]={"error":result.get("error_message"),"request_id":md.get("request_id"),"retry_after_seconds":md.get("retry_after_seconds")}
def turn_metrics(understanding,response,understanding_contract_valid=None):
 u1=(understanding or {}).get("usage") or {};u2=(response or {}).get("usage") or {};pf=int(bool(understanding) and not understanding.get("ok"))+int(bool(response) and not response.get("ok"));cf=int(understanding_contract_valid is False)
 return {"calls":int(bool(understanding) and not understanding.get("skipped"))+int(bool(response) and not response.get("skipped")),"prompt_tokens":int(u1.get("prompt_tokens") or 0)+int(u2.get("prompt_tokens") or 0),"completion_tokens":int(u1.get("completion_tokens") or 0)+int(u2.get("completion_tokens") or 0),"total_tokens":int(u1.get("total_tokens") or 0)+int(u2.get("total_tokens") or 0),"provider_failed_calls":pf,"contract_failed_calls":cf,"functional_failed_calls":cf}
def snapshot(t):return deepcopy(t)
