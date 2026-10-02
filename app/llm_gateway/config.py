from __future__ import annotations

def _get(secrets,key,default=None):
    try:return secrets.get(key,default)
    except Exception:return default

def _as_bool(value, default=False):
    if value is None:return default
    if isinstance(value,bool):return value
    return str(value).strip().casefold() in {"1","true","yes","on"}

def load_gateway_config(secrets)->dict:
    provider=str(_get(secrets,"LLM_PROVIDER","groq")).lower().strip()
    structured=str(_get(secrets,"GROQ_STRUCTURED_OUTPUT_MODE","best_effort")).lower().strip()
    return {
        "provider":provider,
        "fallback_enabled":bool(_get(secrets,"LLM_FALLBACK_ENABLED",False)),
        "fallback_provider":str(_get(secrets,"LLM_FALLBACK_PROVIDER","huggingface")).lower().strip(),
        "max_calls_per_session":max(1,min(100,int(_get(secrets,"LLM_MAX_CALLS_PER_SESSION",20)))),
        "max_total_tokens_per_session":max(500,min(200000,int(_get(secrets,"LLM_MAX_TOTAL_TOKENS_PER_SESSION",12000)))),
        "orchestrator_max_tokens":max(64,min(4096,int(_get(secrets,"LLM_ORCHESTRATOR_MAX_TOKENS",220)))),
        "understanding_max_tokens":max(320,min(4096,int(_get(secrets,"LLM_UNDERSTANDING_MAX_TOKENS",360)))),
        "answer_max_tokens":max(128,min(4096,int(_get(secrets,"LLM_ANSWER_MAX_TOKENS",900)))),
        "evidence_judge_max_tokens":max(64,min(4096,int(_get(secrets,"LLM_EVIDENCE_JUDGE_MAX_TOKENS",360)))),
        "providers":{
            "groq":{"api_key":_get(secrets,"GROQ_API_KEY"),"orchestrator_model":str(_get(secrets,"GROQ_ORCHESTRATOR_MODEL","qwen/qwen3.8-27b")),"answer_model":str(_get(secrets,"GROQ_ANSWER_MODEL","openai/gpt-oss-120b")),"structured_mode":structured,"base_url":"https://api.groq.com/openai/v1/chat/completions"},
            "openrouter":{
                "api_key":_get(secrets,"OPENROUTER_API_KEY"),
                "orchestrator_model":str(_get(secrets,"OPENROUTER_ORCHESTRATOR_MODEL",_get(secrets,"OPENROUTER_MODEL",""))),
                "answer_model":str(_get(secrets,"OPENROUTER_ANSWER_MODEL",_get(secrets,"OPENROUTER_MODEL",""))),
                "structured_mode":str(_get(secrets,"OPENROUTER_STRUCTURED_OUTPUT_MODE","best_effort")).strip().casefold(),
                "base_url":str(_get(secrets,"OPENROUTER_BASE_URL","https://openrouter.ai/api/v1/chat/completions")).strip(),
                "timeout_seconds":max(10,min(180,int(_get(secrets,"OPENROUTER_TIMEOUT_SECONDS",75)))),
                "http_referer":_get(secrets,"OPENROUTER_HTTP_REFERER"),
                "app_title":_get(secrets,"OPENROUTER_APP_TITLE","Arus PrintAssist"),
                "allow_format_fallback":_as_bool(_get(secrets,"OPENROUTER_ALLOW_FORMAT_FALLBACK",True),True),
                "reasoning_effort":str(_get(secrets,"OPENROUTER_REASONING_EFFORT","none")).strip().casefold(),
                "exclude_reasoning":_as_bool(_get(secrets,"OPENROUTER_EXCLUDE_REASONING",True),True),
                "reasoning_fallback":_as_bool(_get(secrets,"OPENROUTER_REASONING_FALLBACK",True),True),
                "reasoning_max_tokens":max(0,min(4096,int(_get(secrets,"OPENROUTER_REASONING_MAX_TOKENS",0)))),
            },
            "huggingface":{
                "token":_get(secrets,"HF_TOKEN"),
                "orchestrator_model":str(_get(secrets,"HF_ORCHESTRATOR_MODEL",_get(secrets,"HF_MODEL",""))),
                "answer_model":str(_get(secrets,"HF_ANSWER_MODEL",_get(secrets,"HF_MODEL",""))),
                "provider":_get(secrets,"HF_PROVIDER"),
                "disable_thinking":_as_bool(_get(secrets,"HF_DISABLE_THINKING",True),True),
                "timeout_seconds":max(10,min(120,int(_get(secrets,"HF_TIMEOUT_SECONDS",75)))),
                "structured_mode":str(_get(secrets,"HF_STRUCTURED_OUTPUT_MODE","json_schema")).strip().casefold(),
            },
        },
    }

def model_for(config, provider, purpose=None, model_role=None):
    """Select a model by explicit role, preserving legacy purpose behavior."""
    role = str(model_role or "").strip().casefold()
    if role == "orchestrator":
        key = "orchestrator_model"
    elif role == "answer":
        key = "answer_model"
    else:
        key = "orchestrator_model" if purpose == "semantic_orchestrator" else "answer_model"
    return config["providers"][provider][key]



