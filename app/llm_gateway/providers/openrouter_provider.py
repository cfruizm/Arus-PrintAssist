from __future__ import annotations
import json,time,urllib.request,urllib.error
from app.llm_gateway.errors import LLMGatewayError
from app.llm_gateway.models import LLMResult
from app.llm_gateway.providers.base import BaseProvider

MODELS_URL="https://openrouter.ai/api/v1/models"
CHAT_URL="https://openrouter.ai/api/v1/chat/completions"

def inspect_key(api_key)->dict:
    raw="" if api_key is None else str(api_key);value=raw.strip()
    return {
        "key_present":bool(raw),"key_length":len(raw),"stripped_length":len(value),
        "prefix_valid":value.startswith("sk-or-v1-"),"leading_or_trailing_whitespace":raw!=value,
        "contains_line_break":"\n" in raw or "\r" in raw,
        "contains_literal_bearer_prefix":value.casefold().startswith("bearer "),
    }

def _request_json(url,api_key,method="GET",body=None,timeout=75,http_referer=None,app_title=None):
    data=None if body is None else json.dumps(body,ensure_ascii=False).encode("utf-8")
    headers={"Authorization":f"Bearer {str(api_key).strip()}","Accept":"application/json","Content-Type":"application/json","User-Agent":"Arus-PrintAssist/1.0"}
    if http_referer:headers["HTTP-Referer"]=str(http_referer).strip()
    if app_title:headers["X-OpenRouter-Title"]=str(app_title).strip()
    request=urllib.request.Request(url,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:
            raw=response.read().decode("utf-8")
            return response.status,json.loads(raw) if raw else {},dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        raw=exc.read().decode("utf-8",errors="replace")
        try:payload=json.loads(raw)
        except Exception:payload={"error":{"message":raw[:1200] or "Provider returned a non-JSON error response."}}
        return exc.code,payload,dict(exc.headers.items()) if exc.headers else {}
    except Exception as exc:
        raise LLMGatewayError("provider_unavailable",f"OpenRouter connection error: {type(exc).__name__}",True) from exc

def _error_result(status,payload,model,purpose,latency,format_mode,headers):
    error=payload.get("error") if isinstance(payload,dict) else None
    message=(error or {}).get("message") if isinstance(error,dict) else None
    provider_code=(error or {}).get("code") if isinstance(error,dict) else None
    metadata=(error or {}).get("metadata") if isinstance(error,dict) else None
    mapping={400:"invalid_request",401:"authentication_failed",402:"credits_exhausted",403:"access_denied",404:"model_not_found",408:"timeout",429:"rate_limited",500:"provider_unavailable",502:"provider_unavailable",503:"provider_unavailable",504:"provider_unavailable"}
    return LLMResult(False,provider="openrouter",model=model,purpose=purpose,latency_ms=latency,error_code=mapping.get(status,"provider_error"),error_message=str(message or f"OpenRouter HTTP {status}")[:1200],metadata={
        "attempted_model":model,"status_code":status,"provider_error_code":provider_code,
        "provider_error_metadata":metadata,"response_format_mode":format_mode,
        "request_id":headers.get("x-request-id") or headers.get("X-Request-Id"),
        "retry_after":headers.get("retry-after") or headers.get("Retry-After"),
    })

def diagnose_openrouter(api_key,configured_model,http_referer=None,app_title=None,timeout_seconds=45)->dict:
    local=inspect_key(api_key)
    result={"endpoint":MODELS_URL,"configured_model":configured_model,"local_validation":local,"request_attempted":False,"status_code":None,"authenticated":False,"model_available":False,"available_model_count":0}
    if not local["key_present"] or local["leading_or_trailing_whitespace"] or local["contains_line_break"] or local["contains_literal_bearer_prefix"]:
        result["error_code"]="invalid_secret_format";return result
    result["request_attempted"]=True
    status,payload,headers=_request_json(MODELS_URL,str(api_key).strip(),timeout=timeout_seconds,http_referer=http_referer,app_title=app_title)
    result["status_code"]=status;result["request_id"]=headers.get("x-request-id") or headers.get("X-Request-Id")
    if status==200:
        models=[str(item.get("id")) for item in payload.get("data",[]) if isinstance(item,dict) and item.get("id")]
        result.update({"authenticated":True,"available_model_count":len(models),"model_available":configured_model in models,"error_code":None if configured_model in models else "configured_model_unavailable"})
        return result
    err=payload.get("error") if isinstance(payload,dict) else {}
    result["provider_error_message"]=str((err or {}).get("message") or "OpenRouter request rejected.")[:500]
    result["error_code"]="openrouter_key_rejected" if status in {401,403} else "openrouter_models_endpoint_failed"
    return result

class OpenRouterProvider(BaseProvider):
    def __init__(self,api_key,base_url=CHAT_URL,structured_mode="best_effort",timeout_seconds=75,http_referer=None,app_title=None,allow_format_fallback=True):
        if not api_key:raise LLMGatewayError("missing_api_key","Falta OPENROUTER_API_KEY.")
        self.api_key=str(api_key).strip();self.base_url=str(base_url or CHAT_URL).strip();self.structured_mode=str(structured_mode or "best_effort").casefold()
        self.timeout_seconds=max(10,min(180,int(timeout_seconds)));self.http_referer=http_referer;self.app_title=app_title;self.allow_format_fallback=bool(allow_format_fallback)
    def _response_format(self,request):
        mode=str(getattr(request,"response_format_mode","auto") or "auto").casefold()
        if mode=="text" or not request.response_schema:return None,"text"
        if mode=="json_object" or (mode=="auto" and self.structured_mode in {"best_effort","json_object"}):return {"type":"json_object"},"json_object"
        return {"type":"json_schema","json_schema":{"name":"structured_response","strict":self.structured_mode=="strict","schema":request.response_schema}},"json_schema"
    def complete(self,request,model):
        response_format,format_mode=self._response_format(request)
        body={"model":model,"messages":request.messages,"max_tokens":max(1,min(4096,int(request.max_tokens))),"temperature":max(0.0,min(2.0,float(request.temperature))),"stream":False}
        if response_format:body["response_format"]=response_format
        effort=str(getattr(request,"reasoning_effort","") or "").casefold()
        if effort in {"low","medium","high"}:body["reasoning"]={"effort":effort}
        started=time.perf_counter();status,data,headers=_request_json(self.base_url,self.api_key,"POST",body,self.timeout_seconds,self.http_referer,self.app_title)
        retried_without_format=False
        if status==400 and response_format and self.allow_format_fallback and self.structured_mode=="best_effort":
            fallback_body=dict(body);fallback_body.pop("response_format",None)
            status,data,headers=_request_json(self.base_url,self.api_key,"POST",fallback_body,self.timeout_seconds,self.http_referer,self.app_title)
            retried_without_format=True;format_mode="text_fallback"
        latency=round((time.perf_counter()-started)*1000,3)
        if status!=200:return _error_result(status,data,model,request.purpose,latency,format_mode,headers)
        choice=(data.get("choices") or [{}])[0];message=choice.get("message") or {};usage=data.get("usage") or {}
        text=str(message.get("content") or "");finish=choice.get("finish_reason")
        metadata={"structured_mode":self.structured_mode,"response_format_mode":format_mode,"structured_fallback_used":retried_without_format,"reasoning_effort":effort or "provider_default","request_id":headers.get("x-request-id") or headers.get("X-Request-Id"),"resolved_model":data.get("model") or model,"upstream_provider":data.get("provider"),"generation_id":data.get("id")}
        if "cost" in usage:metadata["cost"]=usage.get("cost")
        if not text.strip():
            code="empty_truncated_response" if str(finish).casefold() in {"length","max_tokens"} else "empty_response"
            return LLMResult(False,provider="openrouter",model=model,purpose=request.purpose,latency_ms=latency,usage={"prompt_tokens":int(usage.get("prompt_tokens") or 0),"completion_tokens":int(usage.get("completion_tokens") or 0),"total_tokens":int(usage.get("total_tokens") or 0)},finish_reason=finish,error_code=code,error_message="OpenRouter returned empty content.",metadata=metadata)
        return LLMResult(True,text,"openrouter",model,request.purpose,latency,{"prompt_tokens":int(usage.get("prompt_tokens") or 0),"completion_tokens":int(usage.get("completion_tokens") or 0),"total_tokens":int(usage.get("total_tokens") or 0)},finish,metadata=metadata)
