from copy import deepcopy
def empty():return {"calls":0,"failed_calls":0,"prompt_tokens":0,"completion_tokens":0,"total_tokens":0,"latency_ms":0.0,"by_purpose":{},"last_rate_limit":None}
def add_result(t,result):
 if not result:return
 purpose=str(result.get("purpose") or "unknown");usage=result.get("usage") or {};bucket=t["by_purpose"].setdefault(purpose,{"calls":0,"failed_calls":0,"prompt_tokens":0,"completion_tokens":0,"total_tokens":0,"latency_ms":0.0})
 for target in (t,bucket):
  target["calls"]+=1;target["failed_calls"]+=0 if result.get("ok") else 1;target["latency_ms"]+=float(result.get("latency_ms") or 0)
  for key in ("prompt_tokens","completion_tokens","total_tokens"):target[key]+=int(usage.get(key) or 0)
 md=result.get("metadata") or {}
 if result.get("error_code")=="rate_limited" or md.get("provider_error_code")=="rate_limit_exceeded":t["last_rate_limit"]={"error":result.get("error_message"),"remaining_tokens":md.get("rate_limit_remaining_tokens"),"remaining_requests":md.get("rate_limit_remaining_requests"),"request_id":md.get("request_id")}
def turn_metrics(understanding,response):
 u1=(understanding or {}).get("usage") or {};u2=(response or {}).get("usage") or {}
 return {"calls":int(bool(understanding))+int(bool(response)),"prompt_tokens":int(u1.get("prompt_tokens") or 0)+int(u2.get("prompt_tokens") or 0),"completion_tokens":int(u1.get("completion_tokens") or 0)+int(u2.get("completion_tokens") or 0),"total_tokens":int(u1.get("total_tokens") or 0)+int(u2.get("total_tokens") or 0),"understanding_tokens":int(u1.get("total_tokens") or 0),"response_tokens":int(u2.get("total_tokens") or 0),"failed_calls":int(bool(understanding) and not understanding.get("ok"))+int(bool(response) and not response.get("ok"))}
def snapshot(t):return deepcopy(t)
