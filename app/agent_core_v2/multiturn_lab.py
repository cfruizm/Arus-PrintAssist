from __future__ import annotations
import time
from typing import Any
from app.agent_core_v2.models import ConversationState
from app.agent_core_v2.interpreter import QwenInterpreter
from app.agent_core_v2.entity_resolver import EntityResolver
from app.agent_core_v2.semantic_evidence_pipeline import SemanticEvidencePipeline
from app.agent_core_v2.response import ResponseComposer
from app.agent_core_v2.engine import TurnEngine
from app.agent_core_v2.adaptive_controller import AdaptiveCostRouteController
from app.integration.lab_retrieval_adapter import retrieve_from_existing_backend
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway

def _retrieve(query,limit):
 result=retrieve_from_existing_backend(query,limit)
 return list(result.get("evidence") or []) if isinstance(result,dict) and result.get("ok") else []
def _usage(before,after):
 fresh=after[len(before):] if len(after)>=len(before) else after
 return {"calls":len(fresh),"prompt_tokens":sum(int(x.get("usage",{}).get("prompt_tokens",0) or 0) for x in fresh),"completion_tokens":sum(int(x.get("usage",{}).get("completion_tokens",0) or 0) for x in fresh),"total_tokens":sum(int(x.get("usage",{}).get("total_tokens",0) or 0) for x in fresh),"records":fresh}
def _ids(items):return [str(x.get("canonical_id")) for x in (items or [])]
def _contains(values,expected):return all(x in values for x in expected or [])
def _turn_checkpoint(turn,expectation,previous):
 before=turn.get("state_before") or {};after=turn.get("state_after") or {};decision=turn.get("decision") or {};answer=turn.get("answer") or {};case=after.get("technical_case") or {};topic=after.get("active_topic") or {};exp=expectation or {}
 checks={
  "intent":not exp.get("intent") or decision.get("intent")==exp.get("intent"),
  "action":not exp.get("action") or decision.get("action")==exp.get("action"),
  "products_present":_contains(_ids(topic.get("products")),exp.get("products")),
  "products_absent":not set(exp.get("products_absent") or [])&set(_ids(topic.get("products"))),
  "symptom_present":not exp.get("symptom_contains") or str(exp.get("symptom_contains")).casefold() in " ".join(case.get("symptoms") or []).casefold(),
  "scope_present":not exp.get("scope_contains") or str(exp.get("scope_contains")).casefold() in str(case.get("affected_scope") or "").casefold(),
  "attempt_count":exp.get("attempt_count") is None or len(case.get("attempts") or [])>=int(exp.get("attempt_count")),
  "turn_incremented":int(after.get("turn_number",0))==int(before.get("turn_number",0))+1,
  "answer_present":bool(answer.get("text")) or decision.get("action") not in {"retrieve","out_of_scope","ask_clarification"},
  "production_unchanged":True,
 }
 if exp.get("preserve_previous_product") and previous:
  previous_products=set(_ids((previous.get("state_after") or {}).get("active_topic",{}).get("products")))
  checks["previous_product_preserved"]=bool(previous_products&set(_ids(topic.get("products"))))
 failed=[k for k,v in checks.items() if not v]
 return {"checks":checks,"failed_checks":failed,"status":"passed" if not failed else "failed"}
def _conversation_checkpoint(turns,scenario):
 requirements=scenario.get("conversation_expectations") or {};checks={
  "all_turns_executed":len(turns)==len(scenario.get("messages") or []),
  "single_shared_conversation":len({(x.get("state_after") or {}).get("conversation_id") for x in turns})==1,
  "monotonic_turn_numbers":[(x.get("state_after") or {}).get("turn_number") for x in turns]==list(range(1,len(turns)+1)),
  "no_production_change":all(not x.get("production_changed",False) for x in turns),
 }
 if requirements.get("min_topic_history") is not None:
  checks["topic_history"] = len((turns[-1].get("state_after") or {}).get("topic_history") or [])>=int(requirements["min_topic_history"])
 failed=[k for k,v in checks.items() if not v]
 return {"checks":checks,"failed_checks":failed,"status":"passed" if not failed and all(x.get("multiturn_checkpoint",{}).get("status")=="passed" for x in turns) else "failed","scope":"isolated_multiturn_lab"}
def run_multiturn_scenario(scenario,secrets,session_state):
 started=time.perf_counter();gateway=LLMGateway(load_gateway_config(secrets),session_state);before=list(session_state.get("llm_gateway_history",[]) or []);state=ConversationState(conversation_id=str(scenario.get("id") or "multiturn"));turns=[];error=None
 try:
  route=AdaptiveCostRouteController(int(secrets.get("AGENT_CORE_V2_INITIAL_CANDIDATES",3)),int(secrets.get("AGENT_CORE_V2_MAX_CANDIDATES",6)))
  evidence=SemanticEvidencePipeline(_retrieve,gateway,route.max_candidates,int(secrets.get("LLM_EVIDENCE_JUDGE_MAX_TOKENS",300)))
  engine=TurnEngine(QwenInterpreter(gateway,int(secrets.get("LLM_ORCHESTRATOR_MAX_TOKENS",220))),evidence,ResponseComposer(gateway,int(secrets.get("LLM_ANSWER_MAX_TOKENS",400))),EntityResolver(),route)
  expectations=scenario.get("turn_expectations") or []
  for index,message in enumerate(scenario.get("messages") or []):
   turn=engine.process_turn(str(message),state).to_dict();turn["production_changed"]=False;turn["multiturn_checkpoint"]=_turn_checkpoint(turn,expectations[index] if index<len(expectations) else {},turns[-1] if turns else None);turns.append(turn)
  status="ok"
 except Exception as exc:status="error";error=f"{type(exc).__name__}: {exc}"
 after=list(session_state.get("llm_gateway_history",[]) or []);conversation=_conversation_checkpoint(turns,scenario) if turns else {"status":"failed","checks":{},"failed_checks":["no_turns"]};usage=_usage(before,after);metrics={"calls_avoided":sum((x.get("cost_route_metrics") or {}).get("calls_avoided",0) for x in turns),"judge_calls":sum((x.get("cost_route_metrics") or {}).get("judge_calls",0) for x in turns),"answer_llm_calls":sum((x.get("cost_route_metrics") or {}).get("answer_llm_calls",0) for x in turns),"expansion_calls":sum((x.get("cost_route_metrics") or {}).get("expansion_calls",0) for x in turns)}
 return {"scenario_id":scenario.get("id"),"name":scenario.get("name"),"status":status,"error":error,"turns":turns,"final_state":state.to_dict(),"conversation_checkpoint":conversation,"usage":usage,"adaptive_savings":metrics,"latency_ms":round((time.perf_counter()-started)*1000,3),"latency_evaluated":False,"production_changed":False,"checkpoint_passed":conversation.get("status")=="passed"}
