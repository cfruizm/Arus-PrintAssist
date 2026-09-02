from __future__ import annotations
import time,traceback
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

def _retriever(query,limit):
 result=retrieve_from_existing_backend(query,limit)
 if not isinstance(result,dict) or not result.get("ok"):return []
 return list(result.get("evidence") or [])
def _history_usage(before,after):
 fresh=after[len(before):] if len(after)>=len(before) else after
 return {"calls":len(fresh),"prompt_tokens":sum(int(x.get("usage",{}).get("prompt_tokens",0) or 0) for x in fresh),"completion_tokens":sum(int(x.get("usage",{}).get("completion_tokens",0) or 0) for x in fresh),"total_tokens":sum(int(x.get("usage",{}).get("total_tokens",0) or 0) for x in fresh),"records":fresh}
def _friendly_error(exc,usage):
 text=str(exc);record=(usage.get("records") or [{}])[-1];finish=record.get("finish_reason");raw=str(record.get("text") or "")
 if "truncated" in text.casefold() or finish=="length":
  return {"stage":"Interpretación con Qwen","title":"La respuesta estructurada quedó incompleta","explanation":"Qwen alcanzó el límite de salida antes de cerrar el JSON. No se ejecutaron la decisión, el retrieval ni la respuesta técnica.","technical_error":text,"finish_reason":finish,"partial_model_output":raw,"recommended_action":"Reintenta una sola vez después de instalar esta corrección. Si se repite, revisa el modelo configurado y el límite del orquestador."}
 if "JSON" in type(exc).__name__ or "JSON" in text:
  return {"stage":"Validación del contrato","title":"Qwen devolvió un JSON no válido","explanation":"La salida no cumplió el contrato estructurado requerido por Agent Core v2.","technical_error":text,"finish_reason":finish,"partial_model_output":raw,"recommended_action":"No ejecutes otros escenarios hasta corregir el intérprete."}
 return {"stage":"Ejecución del laboratorio","title":"La ejecución no pudo completarse","explanation":"El laboratorio detuvo el escenario sin modificar producción.","technical_error":text,"finish_reason":finish,"partial_model_output":raw,"recommended_action":"Descarga el JSON y comparte el bloque de diagnóstico."}
def _checkpoint(turn,scenario):
 d=turn.get("decision") or {};e=turn.get("evidence") or {};a=turn.get("answer") or {};expected=scenario.get("expected") or {};products=[x.get("canonical_id") for x in turn.get("state_after",{}).get("active_topic",{}).get("products",[])];checks={"intent":not expected.get("intent") or d.get("intent")==expected.get("intent"),"action":not expected.get("action") or d.get("action")==expected.get("action"),"entity":not expected.get("product_id") or expected.get("product_id") in products,"retrieval_contract":d.get("action")!="retrieve" or bool(e.get("counts")),"citable_only_visible":not a.get("citations") or set(a.get("citations") or []).issubset({x.get("id") for x in e.get("citable",[])}),"no_unknown_citations":a.get("mode")!="invalid_citations"};return {"checks":checks,"passed":all(checks.values()),"scope":"real_lab_not_production"}
def run_real_scenario(scenario,secrets,session_state):
 started=time.perf_counter();gateway=LLMGateway(load_gateway_config(secrets),session_state);before=list(session_state.get("llm_gateway_history",[]) or []);state=ConversationState(conversation_id=str(scenario.get("id") or "real-lab"));turns=[];error=None;diagnostic=None
 try:
  engine=TurnEngine(QwenInterpreter(gateway,int(secrets.get("LLM_ORCHESTRATOR_MAX_TOKENS",220))),EvidenceEngine(_retriever),ResponseComposer(gateway,int(secrets.get("LLM_ANSWER_MAX_TOKENS",400))),EntityResolver())
  for message in scenario.get("messages") or []:
   turn=engine.process_turn(str(message),state).to_dict();turn["checkpoint"]=_checkpoint(turn,scenario);turns.append(turn)
  status="ok"
 except Exception as exc:
  status="error";error=f"{type(exc).__name__}: {exc}"
 after=list(session_state.get("llm_gateway_history",[]) or []);usage=_history_usage(before,after)
 if error:diagnostic=_friendly_error(exc,usage)
 return {"scenario_id":scenario.get("id"),"name":scenario.get("name"),"status":status,"error":error,"error_diagnostic":diagnostic,"turns":turns,"final_state":state.to_dict(),"usage":usage,"latency_ms":round((time.perf_counter()-started)*1000,3),"production_changed":False,"checkpoint_passed":bool(turns) and all(x.get("checkpoint",{}).get("passed") for x in turns)}
