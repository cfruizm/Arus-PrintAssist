from __future__ import annotations
import time
from typing import Any
from app.agent_core_v2.models import ConversationState
from app.agent_core_v2.interpreter import QwenInterpreter
from app.agent_core_v2.entity_resolver import EntityResolver
from app.agent_core_v2.evidence import EvidenceEngine
from app.agent_core_v2.response import ResponseComposer
from app.agent_core_v2.engine import TurnEngine
from app.integration.lab_retrieval_adapter import retrieve_from_existing_backend
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway


def _retriever(query:str,limit:int)->list[dict[str,Any]]:
    result=retrieve_from_existing_backend(query,limit)
    if not isinstance(result,dict) or not result.get("ok"):
        return []
    return list(result.get("evidence") or [])


def _used_tokens(before:list,after:list)->dict:
    fresh=after[len(before):] if len(after)>=len(before) else after
    return {
        "calls":len(fresh),
        "prompt_tokens":sum(int(x.get("usage",{}).get("prompt_tokens",0) or 0) for x in fresh),
        "completion_tokens":sum(int(x.get("usage",{}).get("completion_tokens",0) or 0) for x in fresh),
        "total_tokens":sum(int(x.get("usage",{}).get("total_tokens",0) or 0) for x in fresh),
        "records":fresh,
    }


def _checkpoint(turn:dict,scenario:dict)->dict:
    decision=turn.get("decision") or {};evidence=turn.get("evidence") or {};answer=turn.get("answer") or {};state=turn.get("state_after") or {}
    products=[x.get("canonical_id") for x in (state.get("active_topic",{}).get("products") or [])]
    expected=scenario.get("expected") or {};checks={
        "intent": not expected.get("intent") or decision.get("intent")==expected.get("intent"),
        "action": not expected.get("action") or decision.get("action")==expected.get("action"),
        "entity": not expected.get("product_id") or expected.get("product_id") in products,
        "retrieval_contract": (decision.get("action")!="retrieve") or bool(evidence.get("counts")),
        "citable_only_visible": not answer.get("citations") or set(answer.get("citations") or []).issubset({x.get("id") for x in evidence.get("citable",[])}),
        "no_unknown_citations": answer.get("mode") not in {"invalid_citations"},
    }
    return {"checks":checks,"passed":all(checks.values()),"scope":"real_lab_not_production"}


def run_real_scenario(scenario:dict,secrets,session_state)->dict:
    started=time.perf_counter();gateway=LLMGateway(load_gateway_config(secrets),session_state);before=list(session_state.get("llm_gateway_history",[]) or [])
    state=ConversationState(conversation_id=str(scenario.get("id") or "real-lab"))
    engine=TurnEngine(QwenInterpreter(gateway,int(secrets.get("LLM_ORCHESTRATOR_MAX_TOKENS",220))),EvidenceEngine(_retriever),ResponseComposer(gateway,int(secrets.get("LLM_ANSWER_MAX_TOKENS",400))),EntityResolver())
    turns=[]
    try:
        for message in scenario.get("messages") or []:
            result=engine.process_turn(str(message),state).to_dict();result["checkpoint"]=_checkpoint(result,scenario);turns.append(result)
        status="ok"
        error=None
    except Exception as exc:
        status="error";error=f"{type(exc).__name__}: {exc}"
    after=list(session_state.get("llm_gateway_history",[]) or [])
    return {"scenario_id":scenario.get("id"),"name":scenario.get("name"),"status":status,"error":error,"turns":turns,"final_state":state.to_dict(),"usage":_used_tokens(before,after),"latency_ms":round((time.perf_counter()-started)*1000,3),"production_changed":False,"checkpoint_passed":bool(turns) and all(x.get("checkpoint",{}).get("passed") for x in turns)}
