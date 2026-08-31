from __future__ import annotations
import json,time,urllib.request,urllib.error
from app.llm_gateway.errors import LLMGatewayError
from app.llm_gateway.models import LLMResult
from app.llm_gateway.providers.base import BaseProvider

MODELS_URL="https://api.groq.com/openai/v1/models"
CHAT_URL="https://api.groq.com/openai/v1/chat/completions"

def inspect_key(api_key)->dict:
    raw="" if api_key is None else str(api_key); stripped=raw.strip()
    return {"key_present":bool(raw),"key_length":len(raw),"stripped_length":len(stripped),"prefix_valid":stripped.startswith("gsk_"),"leading_or_trailing_whitespace":raw!=stripped,"contains_line_break":"\n" in raw or "\r" in raw,"contains_internal_whitespace":any(ch.isspace() for ch in stripped),"contains_literal_bearer_prefix":stripped.lower().startswith("bearer ")}

def _request_json(url,api_key,method="GET",body=None,timeout=45):
    data=None if body is None else json.dumps(body,ensure_ascii=False).encode("utf-8")
    req=urllib.request.Request(url,data=data,headers={"Authorization":f"Bearer {str(api_key).strip()}","Accept":"application/json","Content-Type":"application/json","User-Agent":"Arus-PrintAssist/1.0"},method=method)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as response:return response.status,json.loads(response.read().decode("utf-8")),dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        raw=exc.read().decode("utf-8",errors="replace")
        try:payload=json.loads(raw)
        except Exception:payload={"error":{"message":raw[:1000] or "Provider returned a non-JSON error response."}}
        return exc.code,payload,dict(exc.headers.items()) if exc.headers else {}

def _error_from_response(status,payload,model):
    error=payload.get("error") if isinstance(payload,dict) else None
    message=(error or {}).get("message") if isinstance(error,dict) else None
    error_type=(error or {}).get("type") if isinstance(error,dict) else None
    code=(error or {}).get("code") if isinstance(error,dict) else None
    text=str(message or f"Groq HTTP {status}")[:1200]
    if status in {401,403}:normalized="authentication_failed";recoverable=False
    elif status==402:normalized="credits_exhausted";recoverable=True
    elif status==404:normalized="model_not_found";recoverable=True
    elif status==429:normalized="rate_limited";recoverable=True
    elif status in {500,502,503,504}:normalized="provider_unavailable";recoverable=True
    elif status==400:normalized="invalid_request";recoverable=False
    else:normalized="provider_error";recoverable=False
    exc=LLMGatewayError(normalized,text,recoverable,status)
    exc.metadata={"attempted_model":model,"provider_error_type":error_type,"provider_error_code":code,"status_code":status}
    return exc

def diagnose_groq(api_key,configured_model)->dict:
    local=inspect_key(api_key);result={"endpoint":MODELS_URL,"configured_model":configured_model,"local_validation":local,"request_attempted":False,"status_code":None,"authenticated":False,"model_available":False,"available_model_count":0,"provider_error_type":None,"provider_error_message":None}
    invalid=not local["key_present"] or not local["prefix_valid"] or local["leading_or_trailing_whitespace"] or local["contains_line_break"] or local["contains_internal_whitespace"] or local["contains_literal_bearer_prefix"]
    if invalid:result["error_code"]="invalid_secret_format";return result
    result["request_attempted"]=True;status,payload,headers=_request_json(MODELS_URL,str(api_key).strip())
    result["status_code"]=status;result["request_id"]=headers.get("x-request-id") or headers.get("X-Request-Id")
    if status==200:
        models=[str(item.get("id")) for item in payload.get("data",[]) if isinstance(item,dict) and item.get("id")]
        result.update({"authenticated":True,"available_model_count":len(models),"model_available":configured_model in models,"available_models":models,"error_code":None if configured_model in models else "configured_model_unavailable"});return result
    err=payload.get("error") if isinstance(payload,dict) else {};result["provider_error_type"]=(err or {}).get("type");result["provider_error_message"]=str((err or {}).get("message") or "Authentication request was rejected.")[:500];result["error_code"]="groq_key_rejected" if status in {401,403} else "groq_models_endpoint_failed";return result

class GroqProvider(BaseProvider):
    def __init__(self,api_key:str,base_url:str=CHAT_URL,structured_mode:str="best_effort"):
        if not api_key:raise LLMGatewayError("missing_api_key","Falta GROQ_API_KEY.")
        self.api_key=str(api_key).strip();self.base_url=base_url;self.structured_mode=structured_mode
    def _response_format(self,request,model):
        if not request.response_schema:return None,"text"
        # GPT-OSS is evaluated in best-effort with JSON Object mode. Python still
        # validates the complete semantic schema after the response.
        if model.startswith("openai/gpt-oss-") and self.structured_mode!="strict":
            return {"type":"json_object"},"json_object"
        return {"type":"json_schema","json_schema":{"name":"structured_response","strict":self.structured_mode=="strict","schema":request.response_schema}},"json_schema"
    def complete(self,request,model):
        body={"model":model,"messages":request.messages,"max_completion_tokens":max(32,min(4096,int(request.max_tokens))),"temperature":max(0.0,min(2.0,float(request.temperature))),"stream":False}
        response_format,format_mode=self._response_format(request,model)
        if response_format:body["response_format"]=response_format
        if model.startswith("openai/gpt-oss-"):
            body["reasoning_effort"]="none"
        started=time.perf_counter();status,data,headers=_request_json(self.base_url,self.api_key,"POST",body,45)
        if status!=200:raise _error_from_response(status,data,model)
        choice=(data.get("choices") or [{}])[0];message=choice.get("message") or {};usage=data.get("usage") or {}
        return LLMResult(True,str(message.get("content") or ""),"groq",model,request.purpose,round((time.perf_counter()-started)*1000,3),{"prompt_tokens":int(usage.get("prompt_tokens") or 0),"completion_tokens":int(usage.get("completion_tokens") or 0),"total_tokens":int(usage.get("total_tokens") or 0)},choice.get("finish_reason"),metadata={"structured_mode":self.structured_mode,"response_format_mode":format_mode,"reasoning_effort":"none" if model.startswith("openai/gpt-oss-") else None,"rate_limit_remaining_requests":headers.get("x-ratelimit-remaining-requests"),"rate_limit_remaining_tokens":headers.get("x-ratelimit-remaining-tokens"),"request_id":headers.get("x-request-id")})
