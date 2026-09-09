from copy import deepcopy
def empty():return {"calls":0,"provider_failed_calls":0,"contract_failed_calls":0,"functional_failed_calls":0,"prompt_tokens":0,"completion_tokens":0,"total_tokens":0,"latency_ms":0.0,"by_purpose":{},"last_rate_limit":None}
def add_result(t,result,contract_valid=None):
 if not result or result.get("skipped"):return
 purpose=str(result.get("purpose") or "unknown");usage=result.get("usage") or {};b=t["by_purpose"].setdefault(purpose,{"calls":0,"provider_failed_calls":0,"contract_failed_calls":0,"prompt_tokens":0,"completion_tokens":0,"total_tokens":0,"latency_ms":0.0})
 provider_ok=bool(result.get("ok"));contract_ok=provider_ok if contract_valid is None else bool(contract_valid);functional_ok=provider_ok and contract_ok
 for target in (t,b):
  target["calls"]+=1;target["provider_failed_calls"]+=0 if provider_ok else 1;target["contract_failed_calls"]+=0 if contract_ok else 1;target["latency_ms"]+=float(result.get("latency_ms") or 0)
  for k in ("prompt_tokens","completion_tokens","total_tokens"):target[k]+=int(usage.get(k) or 0)
 t["functional_failed_calls"]+=0 if functional_ok else 1
 md=result.get("metadata") or {}
 if result.get("error_code")=="rate_limited" or md.get("provider_error_code")=="rate_limit_exceeded":t["last_rate_limit"]={"error":result.get("error_message"),"request_id":md.get("request_id")}
def turn_metrics(understanding,response,understanding_contract_valid=None):
 u1=(understanding or {}).get("usage") or {};u2=(response or {}).get("usage") or {};provider_fail=int(bool(understanding) and not understanding.get("ok"))+int(bool(response) and not response.get("ok"));contract_fail=int(understanding_contract_valid is False)
 return {"calls":int(bool(understanding) and not understanding.get("skipped"))+int(bool(response) and not response.get("skipped")),"prompt_tokens":int(u1.get("prompt_tokens") or 0)+int(u2.get("prompt_tokens") or 0),"completion_tokens":int(u1.get("completion_tokens") or 0)+int(u2.get("completion_tokens") or 0),"total_tokens":int(u1.get("total_tokens") or 0)+int(u2.get("total_tokens") or 0),"provider_failed_calls":provider_fail,"contract_failed_calls":contract_fail,"functional_failed_calls":provider_fail+contract_fail}
def snapshot(t):return deepcopy(t)
