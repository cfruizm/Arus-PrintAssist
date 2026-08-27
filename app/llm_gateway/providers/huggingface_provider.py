from __future__ import annotations
import time
from huggingface_hub import InferenceClient
from app.llm_gateway.errors import LLMGatewayError,normalize_error
from app.llm_gateway.models import LLMResult
from app.llm_gateway.providers.base import BaseProvider

class HuggingFaceProvider(BaseProvider):
    def __init__(self,token,provider=None):
        if not token:raise LLMGatewayError("missing_api_key","Falta HF_TOKEN.")
        self.client=InferenceClient(token=token,provider=provider) if provider else InferenceClient(token=token)
    def complete(self,request,model):
        kwargs={"model":model,"messages":request.messages,"max_tokens":max(32,min(4096,int(request.max_tokens))),"temperature":max(1e-8,float(request.temperature)),"stream":False}
        started=time.perf_counter()
        try:response=self.client.chat_completion(**kwargs)
        except Exception as exc:raise normalize_error(exc) from exc
        try:choice=response.choices[0];text=str(choice.message.content or "");finish=choice.finish_reason
        except Exception:raise LLMGatewayError("invalid_response","Respuesta HF no reconocida.")
        usage=getattr(response,"usage",None);usage_dict={"prompt_tokens":int(getattr(usage,"prompt_tokens",0) or 0),"completion_tokens":int(getattr(usage,"completion_tokens",0) or 0),"total_tokens":int(getattr(usage,"total_tokens",0) or 0)}
        return LLMResult(True,text,"huggingface",model,request.purpose,round((time.perf_counter()-started)*1000,3),usage_dict,finish)
