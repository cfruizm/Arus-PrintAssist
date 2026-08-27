from __future__ import annotations
import json,re,time
from app.agent_core.semantic_prompt import build_semantic_orchestrator_messages
from app.agent_core.semantic_schema import validate_semantic_decision

def _extract_json(text:str)->dict:
    value=str(text or "").strip()
    if value.startswith("```"):
        value=re.sub(r"^```(?:json)?\s*|\s*```$","",value,flags=re.I|re.S).strip()
    try:return json.loads(value)
    except Exception:
        match=re.search(r"\{.*\}",value,re.S)
        if not match:raise ValueError("Model did not return a JSON object")
        return json.loads(match.group(0))

def evaluate_semantic_turn(message:str,case_state:dict,recent_turns:list[dict],llm_call)->dict:
    started=time.perf_counter();messages=build_semantic_orchestrator_messages(message,case_state,recent_turns)
    raw=llm_call(messages);data=_extract_json(raw);decision=validate_semantic_decision(data)
    return {"input":message,"decision":decision.to_dict(),"raw_model_output":str(raw)[:4000],"latency_ms":round((time.perf_counter()-started)*1000,3),"llm_calls":1,"retrieval_calls":0,"production_response_changed":False}
