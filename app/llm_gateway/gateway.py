from __future__ import annotations
from app.llm_gateway.config import model_for
from app.llm_gateway.errors import LLMGatewayError
from app.llm_gateway.models import LLMResult
from app.llm_gateway.providers.groq_provider import GroqProvider
from app.llm_gateway.providers.huggingface_provider import HuggingFaceProvider

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
    def complete(self,request):
        self._budget();primary=self.config["provider"]
        try:
            result=self._provider(primary).complete(request,model_for(self.config,primary,request.purpose));self._record(result);return result
        except LLMGatewayError as exc:
            if not (exc.recoverable and self.config["fallback_enabled"] and self.config["fallback_provider"]!=primary):
                result=LLMResult(False,provider=primary,purpose=request.purpose,error_code=exc.code,error_message=str(exc));self._record(result);return result
            fallback=self.config["fallback_provider"]
            try:
                result=self._provider(fallback).complete(request,model_for(self.config,fallback,request.purpose));result.fallback_used=True;result.fallback_provider=fallback;self._record(result);return result
            except LLMGatewayError as second:
                result=LLMResult(False,provider=fallback,purpose=request.purpose,error_code=second.code,error_message=str(second),fallback_used=True,fallback_provider=fallback);self._record(result);return result
