from __future__ import annotations
from dataclasses import asdict
from app.integration.session_adapter_v1 import get_or_create_router_shadow_state

def export_case_state(chat_session_state)->dict:
    return asdict(get_or_create_router_shadow_state(chat_session_state))

def build_hf_llm_call(hf_client,call_hf_chat_completion,extract_llm_answer_text):
    def invoke(messages):
        response=call_hf_chat_completion(hf_client,messages)
        text=extract_llm_answer_text(response)
        if not text:raise ValueError("Empty semantic orchestrator response")
        return text
    return invoke
