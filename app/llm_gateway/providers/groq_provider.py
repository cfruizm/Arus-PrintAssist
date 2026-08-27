from __future__ import annotations
import json,time,urllib.request,urllib.error
from app.llm_gateway.errors import LLMGatewayError,normalize_error
from app.llm_gateway.models import LLMResult
from app.llm_gateway.providers.base import BaseProvider

class GroqProvider(BaseProvider):
    def __init__(self,api_key:str,base_url:str,structured_mode:str="best_effort"):
        if not api_key:raise LLMGatewayError("missing_api_key","Falta GROQ_API_KEY.")
        self.api_key=api_key;self.base_url=base_url;self.structured_mode=structured_mode
    def complete(self,request,model):
        body={"model":model,"messages":request.messages,"max_tokens":max(32,min(4096,int(request.max_tokens))),"temperature":max(1e-8,float(request.temperature)),"stream":False}
        if request.response_schema:
            body["response_format"]={"type":"json_schema","json_schema":{"name":"structured_response","strict":self.structured_mode=="strict","schema":request.response_schema}}
        raw=json.dumps(body,ensure_ascii=False).encode("utf-8")
        req=urllib.request.Request(self.base_url,data=raw,headers={"Authorization":f"Bearer {self.api_key}","Content-Type":"application/json"},method="POST")
        started=time.perf_counter()
        try:
            with urllib.request.urlopen(req,timeout=45) as response:data=json.loads(response.read().decode("utf-8"));headers=dict(response.headers.items())
        except urllib.error.HTTPError as exc:
            try:detail=exc.read().decode("utf-8")
            except Exception:detail=str(exc)
            wrapped=RuntimeError(detail);wrapped.response=type("R",(),{"status_code":exc.code})();raise normalize_error(wrapped) from exc
        except Exception as exc:raise normalize_error(exc) from exc
        choice=(data.get("choices") or [{}])[0];message=choice.get("message") or {};usage=data.get("usage") or {}
        return LLMResult(True,str(message.get("content") or ""),"groq",model,request.purpose,round((time.perf_counter()-started)*1000,3),{"prompt_tokens":int(usage.get("prompt_tokens") or 0),"completion_tokens":int(usage.get("completion_tokens") or 0),"total_tokens":int(usage.get("total_tokens") or 0)},choice.get("finish_reason"),metadata={"structured_mode":self.structured_mode,"rate_limit_remaining_requests":headers.get("x-ratelimit-remaining-requests"),"rate_limit_remaining_tokens":headers.get("x-ratelimit-remaining-tokens")})
