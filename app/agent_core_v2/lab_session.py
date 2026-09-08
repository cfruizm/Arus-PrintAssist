from __future__ import annotations
from copy import deepcopy
from typing import Any
from app.agent_core_v2.models import ConversationState,InterpreterProposal
from app.agent_core_v2.interpreter import QwenInterpreter
from app.agent_core_v2.entity_resolver import EntityResolver
from app.agent_core_v2.semantic_evidence_pipeline import SemanticEvidencePipeline
from app.agent_core_v2.response import ResponseComposer
from app.agent_core_v2.engine import TurnEngine
from app.agent_core_v2.adaptive_controller import AdaptiveCostRouteController
from app.integration.lab_retrieval_adapter import retrieve_from_existing_backend, retrieve_exact_document
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway
SESSION_KEY="agent_core_v2_free_lab"

def _retrieve(query,limit,source_identity=None):
 result=retrieve_exact_document(source_identity,limit) if source_identity else retrieve_from_existing_backend(query,limit)
 return list(result.get("evidence") or []) if isinstance(result,dict) and result.get("ok") else []
def _new_store():return {"state":ConversationState(conversation_id="free-lab"),"messages":[],"turns":[],"errors":[]}
def get_store(s):
 if SESSION_KEY not in s:s[SESSION_KEY]=_new_store()
 return s[SESSION_KEY]
def reset_store(s):s[SESSION_KEY]=_new_store();return s[SESSION_KEY]
def build_engine(secrets,s):
 gateway=LLMGateway(load_gateway_config(secrets),s);route=AdaptiveCostRouteController(int(secrets.get("AGENT_CORE_V2_INITIAL_CANDIDATES",3)),int(secrets.get("AGENT_CORE_V2_MAX_CANDIDATES",6)));evidence=SemanticEvidencePipeline(_retrieve,gateway,route.max_candidates,int(secrets.get("LLM_EVIDENCE_JUDGE_MAX_TOKENS",300)));return TurnEngine(QwenInterpreter(gateway,int(secrets.get("LLM_ORCHESTRATOR_MAX_TOKENS",240))),evidence,ResponseComposer(gateway,int(secrets.get("LLM_ANSWER_MAX_TOKENS",900))),EntityResolver(),route)
def _append(store,user_text,result):
 answer=str((result.get("answer") or {}).get("text") or "").strip() or "El turno fue registrado, pero no produjo una respuesta visible.";store["messages"].extend([{"role":"user","content":user_text},{"role":"assistant","content":answer}]);store["turns"].append(result);return result
def process_message(message,secrets,s):
 store=get_store(s);text=" ".join(str(message or "").split())
 if not text:raise ValueError("El mensaje no puede estar vacío.")
 try:return _append(store,text,build_engine(secrets,s).process_turn(text,store["state"]).to_dict())
 except Exception as exc:store["errors"].append({"message":text,"type":type(exc).__name__,"detail":str(exc)});raise

def request_escalation(secrets,s):
 store=get_store(s);engine=build_engine(secrets,s);proposal=InterpreterProposal(conversation_act="escalation",intent="escalation",requested_action="start_escalation",topic_relation="same_topic",entities=[],facts=[],clarification_question=None,confidence=1.0,reasoning_summary="explicit_ui_action")
 # Bypass language interpretation only. Reuse canonical reconciler, transition engine, response composer and shared state.
 before=deepcopy(store["state"].to_dict());decision=engine.reconciler.reconcile(proposal,store["state"],[]);store["state"].turn_number+=1;audit=engine.transitions.apply(store["state"],decision,increment_turn=False);answer=engine.response_composer.compose_conversation("Solicitar escalamiento",decision,store["state"]);result={"input":"[Acción de interfaz] Solicitar escalamiento","state_before":before,"proposal":proposal.__dict__,"decision":decision.to_dict(),"state_after":deepcopy(store["state"].to_dict()),"response_directive":{"action":decision.action,"intent":decision.intent,"requires_retrieval":False,"adaptive_route":"explicit_escalation_action"},"audit":audit,"evidence":{},"answer":answer,"cost_route_metrics":{"retrieval_calls":0,"judge_calls":0,"answer_llm_calls":1,"expansion_calls":0,"calls_avoided":2,"route_plans":[{"route":"explicit_escalation_action"}]},"semantic_interpretation_trace":{"bypassed":True,"reason":"explicit_ui_action"},"retrieval_query_trace":{}}
 return _append(store,"Solicitar escalamiento",result)
def cancel_current_flow(secrets,s):
 store=get_store(s);engine=build_engine(secrets,s);proposal=InterpreterProposal(conversation_act="cancel",intent="cancel",requested_action="cancel_all",topic_relation="same_topic",entities=[],facts=[],clarification_question=None,confidence=1.0,reasoning_summary="explicit_ui_action");before=deepcopy(store["state"].to_dict());decision=engine.reconciler.reconcile(proposal,store["state"],[]);store["state"].turn_number+=1;audit=engine.transitions.apply(store["state"],decision,increment_turn=False);answer=engine.response_composer.compose_conversation("Cancelar flujo actual",decision,store["state"]);result={"input":"[Acción de interfaz] Cancelar flujo actual","state_before":before,"proposal":proposal.__dict__,"decision":decision.to_dict(),"state_after":deepcopy(store["state"].to_dict()),"response_directive":{"action":decision.action,"intent":decision.intent,"requires_retrieval":False,"adaptive_route":"explicit_cancel_action"},"audit":audit,"evidence":{},"answer":answer,"cost_route_metrics":{"retrieval_calls":0,"judge_calls":0,"answer_llm_calls":1,"expansion_calls":0,"calls_avoided":2,"route_plans":[{"route":"explicit_cancel_action"}]},"semantic_interpretation_trace":{"bypassed":True,"reason":"explicit_ui_action"},"retrieval_query_trace":{}}
 return _append(store,"Cancelar flujo actual",result)
def public_state(store):return deepcopy(store["state"].to_dict())
def export_session(s):
 store=get_store(s);return {"format":"agent_core_v2_free_lab_session","messages":deepcopy(store["messages"]),"turns":deepcopy(store["turns"]),"state":public_state(store),"errors":deepcopy(store["errors"]),"production_changed":False}
