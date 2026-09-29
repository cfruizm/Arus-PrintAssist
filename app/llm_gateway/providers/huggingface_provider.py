from __future__ import annotations
import time
from huggingface_hub import InferenceClient
from app.llm_gateway.errors import LLMGatewayError,normalize_error
from app.llm_gateway.models import LLMResult
from app.llm_gateway.providers.base import BaseProvider

class HuggingFaceProvider(BaseProvider):
    def __init__(self,token,provider=None,disable_thinking=True,timeout_seconds=75,structured_mode="json_schema"):
        if not token:raise LLMGatewayError("missing_api_key","Falta HF_TOKEN.")
        self.provider=provider
        self.disable_thinking=bool(disable_thinking)
        self.structured_mode=str(structured_mode or "json_schema").casefold()
        self.timeout_seconds=max(10,min(120,int(timeout_seconds)))
        kwargs={"token":token,"timeout":self.timeout_seconds}
        if provider:kwargs["provider"]=provider
        self.client=InferenceClient(**kwargs)

    def _response_format(self,request):
        mode=str(getattr(request,"response_format_mode","auto") or "auto").casefold()
        if mode=="text" or not request.response_schema:return None,"text"
        if mode=="json_object" or self.structured_mode=="json_object":return {"type":"json_object"},"json_object"
        return {"type":"json_schema","json_schema":{"name":"structured_response","strict":True,"schema":request.response_schema}},"json_schema"

    def complete(self,request,model):
        response_format,format_mode=self._response_format(request)
        kwargs={
            "model":model,
            "messages":request.messages,
            "max_tokens":max(32,min(4096,int(request.max_tokens))),
            "temperature":max(1e-8,float(request.temperature)),
            "stream":False,
        }
        if response_format:kwargs["response_format"]=response_format
        if self.disable_thinking:
            kwargs["extra_body"]={"chat_template_kwargs":{"enable_thinking":False}}
        started=time.perf_counter()
        try:response=self.client.chat_completion(**kwargs)
        except Exception as exc:raise normalize_error(exc) from exc
        latency=round((time.perf_counter()-started)*1000,3)
        try:
            choice=response.choices[0];message=choice.message;text=str(message.content or "");finish=choice.finish_reason
        except Exception:raise LLMGatewayError("invalid_response","Respuesta HF no reconocida.")
        usage=getattr(response,"usage",None);usage_dict={"prompt_tokens":int(getattr(usage,"prompt_tokens",0) or 0),"completion_tokens":int(getattr(usage,"completion_tokens",0) or 0),"total_tokens":int(getattr(usage,"total_tokens",0) or 0)}
        metadata={"provider_route":self.provider,"thinking_disabled":self.disable_thinking,"response_format_mode":format_mode,"timeout_seconds":self.timeout_seconds}
        if not text.strip():
            code="empty_truncated_response" if str(finish).casefold()=="length" else "empty_response"
            exc=LLMGatewayError(code,"Hugging Face devolvió contenido vacío"+(" al agotar el presupuesto de salida." if code=="empty_truncated_response" else "."),True if code=="empty_truncated_response" else False)
            exc.metadata={**metadata,"finish_reason":finish,"usage":usage_dict,"attempted_model":model}
            raise exc
        return LLMResult(True,text,"huggingface",model,request.purpose,latency,usage_dict,finish,metadata=metadata)
