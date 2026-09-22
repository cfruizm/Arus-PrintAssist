def empty():return {"calls":0,"prompt_tokens":0,"completion_tokens":0,"total_tokens":0,"failed_calls":0,"by_purpose":{}}
def normalize(x):return x if isinstance(x,dict) else empty()
def add_result(t,r,valid=True):
    if not r or r.get("skipped"):return
    u=r.get("usage") or {};t["calls"]+=1;t["prompt_tokens"]+=int(u.get("prompt_tokens",0));t["completion_tokens"]+=int(u.get("completion_tokens",0));t["total_tokens"]+=int(u.get("total_tokens",0));t["failed_calls"]+=0 if r.get("ok") else 1
    p=str(r.get("purpose") or "unknown");d=t["by_purpose"].setdefault(p,{"calls":0,"total_tokens":0,"failed_calls":0});d["calls"]+=1;d["total_tokens"]+=int(u.get("total_tokens",0));d["failed_calls"]+=0 if r.get("ok") else 1
def snapshot(t):return normalize(t.copy())
