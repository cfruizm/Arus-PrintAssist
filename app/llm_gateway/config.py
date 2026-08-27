from __future__ import annotations

def _get(secrets,key,default=None):
    try:return secrets.get(key,default)
    except Exception:return default

def load_gateway_config(secrets)->dict:
    provider=str(_get(secrets,"LLM_PROVIDER","groq")).lower().strip()
    structured=str(_get(secrets,"GROQ_STRUCTURED_OUTPUT_MODE","best_effort")).lower().strip()
    return {
        "provider":provider,
        "fallback_enabled":bool(_get(secrets,"LLM_FALLBACK_ENABLED",False)),
        "fallback_provider":str(_get(secrets,"LLM_FALLBACK_PROVIDER","huggingface")).lower().strip(),
        "max_calls_per_session":max(1,min(100,int(_get(secrets,"LLM_MAX_CALLS_PER_SESSION",20)))),
        "max_total_tokens_per_session":max(500,min(200000,int(_get(secrets,"LLM_MAX_TOTAL_TOKENS_PER_SESSION",12000)))),
        "providers":{
            "groq":{"api_key":_get(secrets,"GROQ_API_KEY"),"orchestrator_model":str(_get(secrets,"GROQ_ORCHESTRATOR_MODEL","qwen/qwen3.8-27b")),"answer_model":str(_get(secrets,"GROQ_ANSWER_MODEL","openai/gpt-oss-120b")),"structured_mode":structured,"base_url":"https://api.groq.com/openai/v1/chat/completions"},
            "huggingface":{"token":_get(secrets,"HF_TOKEN"),"orchestrator_model":str(_get(secrets,"HF_ORCHESTRATOR_MODEL",_get(secrets,"HF_MODEL",""))),"answer_model":str(_get(secrets,"HF_ANSWER_MODEL",_get(secrets,"HF_MODEL",""))),"provider":_get(secrets,"HF_PROVIDER")},
        },
    }

def model_for(config,provider,purpose):
    key="orchestrator_model" if purpose=="semantic_orchestrator" else "answer_model"
    return config["providers"][provider][key]
