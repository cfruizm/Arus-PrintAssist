from __future__ import annotations
import time
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
def _ret(q,n):
 r=retrieve_from_existing_backend(q,n);return list(r.get("evidence") or []) if isinstance(r,dict) and r.get("ok") else []
def _usage(b,a):
 f=a[len(b):] if len(a)>=len(b) else a;return {"calls":len(f),"prompt_tokens":sum(int(x.get("usage",{}).get("prompt_tokens",0) or 0) for x in f),"completion_tokens":sum(int(x.get("usage",{}).get("completion_tokens",0) or 0) for x in f),"total_tokens":sum(int(x.get("usage",{}).get("total_tokens",0) or 0) for x in f),"records":f}
def _grade(t,s):
 d=t.get("decision") or {};e=t.get("evidence") or {};a=t.get("answer") or {};m=t.get("cost_route_metrics") or {};exp=s.get("expected") or {};products=[x.get("canonical_id") for x in t.get("state_after",{}).get("active_topic",{}).get("products",[])];approved={x.get("id") for x in e.get("citable",[])};requires=bool(d.get("requires_retrieval"));checks={"intent":not exp.get("intent") or d.get("intent")==exp.get("intent"),"action":not exp.get("action") or d.get("action")==exp.get("action"),"entity":not exp.get("product_id") or exp.get("product_id") in products,"answer_present":bool(a.get("text")) or d.get("action") not in {"retrieve","out_of_scope"},"judge_only_when_needed":(requires and m.get("judge_calls",0)>=1) or (not requires and m.get("judge_calls",0)==0),"citation_integrity":set(a.get("citations") or []).issubset(approved),"response_not_truncated":a.get("finish_reason")!="length"}
 failed=[k for k,v in checks.items() if not v];status="failed" if failed else "passed" if (not requires or e.get("direct")) else "partial";return {"checks":checks,"failed_checks":failed,"status":status,"latency_evaluated":False,"scope":"real_lab_not_production"}
def run_real_scenario(scenario,secrets,session_state):
 start=time.perf_counter();g=LLMGateway(load_gateway_config(secrets),session_state);before=list(session_state.get("llm_gateway_history",[]) or []);state=ConversationState(conversation_id=str(scenario.get("id") or "lab"));turns=[];err=None
 try:
  route=AdaptiveCostRouteController(int(secrets.get("AGENT_CORE_V2_INITIAL_CANDIDATES",3)),int(secrets.get("AGENT_CORE_V2_MAX_CANDIDATES",6)));evidence=SemanticEvidencePipeline(_ret,g,route.max_candidates,int(secrets.get("LLM_EVIDENCE_JUDGE_MAX_TOKENS",300)));eng=TurnEngine(QwenInterpreter(g,int(secrets.get("LLM_ORCHESTRATOR_MAX_TOKENS",220))),evidence,ResponseComposer(g,int(secrets.get("LLM_ANSWER_MAX_TOKENS",400))),EntityResolver(),route)
  for msg in scenario.get("messages") or []:
   t=eng.process_turn(str(msg),state).to_dict();t["functional_checkpoint"]=_grade(t,scenario);turns.append(t)
  status="ok"
 except Exception as x:status="error";err=f"{type(x).__name__}: {x}"
 after=list(session_state.get("llm_gateway_history",[]) or []);grades=[x.get("functional_checkpoint",{}).get("status") for x in turns];overall="failed" if status=="error" or "failed" in grades else "partial" if "partial" in grades else "passed";savings={"calls_avoided":sum((x.get("cost_route_metrics") or {}).get("calls_avoided",0) for x in turns),"expansions":sum((x.get("cost_route_metrics") or {}).get("expansion_calls",0) for x in turns),"answer_llm_calls":sum((x.get("cost_route_metrics") or {}).get("answer_llm_calls",0) for x in turns),"judge_calls":sum((x.get("cost_route_metrics") or {}).get("judge_calls",0) for x in turns)}
 return {"scenario_id":scenario.get("id"),"name":scenario.get("name"),"status":status,"error":err,"turns":turns,"final_state":state.to_dict(),"usage":_usage(before,after),"adaptive_savings":savings,"latency_ms":round((time.perf_counter()-start)*1000,3),"latency_evaluated":False,"production_changed":False,"functional_result":overall,"checkpoint_passed":overall=="passed"}
