from __future__ import annotations
from app.llm_gateway.config import model_for
from app.llm_gateway.errors import LLMGatewayError
from app.llm_gateway.models import LLMResult
import time
from app.llm_gateway.providers.groq_provider import GroqProvider
from app.llm_gateway.providers.huggingface_provider import HuggingFaceProvider


SESSION_KEYS=("llm_gateway_calls","llm_gateway_tokens","llm_gateway_history","llm_gateway_output_ledger")
def reset_gateway_session(session_state):
    if session_state is None:return
    for key in SESSION_KEYS:session_state.pop(key,None)

class LLMGateway:
    def __init__(self,config,session_state=None):self.config=config;self.session=session_state
    def _provider(self,name):
        cfg=self.config["providers"][name]
        if name=="groq":return GroqProvider(cfg["api_key"],cfg["base_url"],cfg["structured_mode"])
        if name=="huggingface":return HuggingFaceProvider(cfg["token"],cfg.get("provider"))
        raise LLMGatewayError("unsupported_provider",f"Proveedor no soportado: {name}")
    def _budget(self):
        if self.session is None:return
        calls=int(self.session.get("llm_gateway_calls",0));tokens=int(self.session.get("llm_gateway_tokens",0))
        if calls>=self.config["max_calls_per_session"]:raise LLMGatewayError("session_call_budget_exhausted","Límite de llamadas de la sesión alcanzado.")
        if tokens>=self.config["max_total_tokens_per_session"]:raise LLMGatewayError("session_token_budget_exhausted","Límite de tokens de la sesión alcanzado.")
    def _record(self,result):
        if self.session is None:return
        self.session["llm_gateway_calls"]=int(self.session.get("llm_gateway_calls",0))+1
        self.session["llm_gateway_tokens"]=int(self.session.get("llm_gateway_tokens",0))+int(result.usage.get("total_tokens",0))
        history=list(self.session.get("llm_gateway_history",[]) or []);history.append(result.to_dict());self.session["llm_gateway_history"]=history[-100:]
    def _error_result(self,provider,model,purpose,exc,fallback_used=False,fallback_provider=None):
        metadata=dict(getattr(exc,"metadata",{}) or {});metadata.setdefault("attempted_model",model);metadata.setdefault("status_code",getattr(exc,"status_code",None))
        return LLMResult(False,provider=provider,model=model,purpose=purpose,error_code=exc.code,error_message=str(exc),fallback_used=fallback_used,fallback_provider=fallback_provider,metadata=metadata)
    def _reserve_output(self,request):
        purpose=str(request.purpose or "").casefold();role=str(getattr(request,"model_role","") or "").casefold()
        if "judge" in purpose: configured=int(self.config.get("evidence_judge_max_tokens",360))
        elif role=="orchestrator" or "understanding" in purpose or "orchestrator" in purpose: configured=int(self.config.get("orchestrator_max_tokens",220))
        else: configured=int(self.config.get("answer_max_tokens",900))
        requested=max(1,int(request.max_tokens or configured));granted=min(requested,configured)
        request.max_tokens=granted
        setattr(request,"_token_debug",{"requested_max_tokens":requested,"configured_cap":configured,"effective_max_tokens":granted,"policy":"role_cap_v2_no_rolling_clamp"})
        return request
    def _record_output(self,result):
        if self.session is None:return
        now=time.time();ledger=[x for x in list(self.session.get("llm_gateway_output_ledger",[]) or []) if now-float(x.get("time",0))<60]
        used=int((result.usage or {}).get("completion_tokens",0) or 0)
        if used:ledger.append({"time":now,"tokens":used,"purpose":result.purpose})
        self.session["llm_gateway_output_ledger"]=ledger
    def complete(self,request):
        self._budget();request=self._reserve_output(request);primary=self.config["provider"];primary_model=model_for(self.config,primary,request.purpose,getattr(request,"model_role",None))
        try:
            result=self._provider(primary).complete(request,primary_model);result.metadata={**dict(result.metadata or {}),"token_budget_debug":getattr(request,"_token_debug",{})};self._record(result);self._record_output(result);return result
        except LLMGatewayError as exc:
            if not (exc.recoverable and self.config["fallback_enabled"] and self.config["fallback_provider"]!=primary):
                result=self._error_result(primary,primary_model,request.purpose,exc);self._record(result);return result
            fallback=self.config["fallback_provider"];fallback_model=model_for(self.config,fallback,request.purpose,getattr(request,"model_role",None))
            try:
                result=self._provider(fallback).complete(request,fallback_model);result.fallback_used=True;result.fallback_provider=fallback;self._record(result);return result
            except LLMGatewayError as second:
                result=self._error_result(fallback,fallback_model,request.purpose,second,True,fallback);self._record(result);return result



