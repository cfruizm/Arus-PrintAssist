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
def _ids(x):return [str(i.get("canonical_id")) for i in x or []]
def _checkpoint(t,e):
 b=t.get("state_before") or {};a=t.get("state_after") or {};d=t.get("decision") or {};answer=t.get("answer") or {};q=t.get("retrieval_query_trace") or {};topic=a.get("active_topic") or {};case=a.get("technical_case") or {};exp=e or {};attempts=case.get("attempts") or [];checks={"intent":not exp.get("intent") or d.get("intent")==exp.get("intent"),"action":not exp.get("action") or d.get("action")==exp.get("action"),"products_present":all(x in _ids(topic.get("products")) for x in exp.get("products") or []),"products_absent":not set(exp.get("products_absent") or [])&set(_ids(topic.get("products"))),"symptom_present":not exp.get("symptom_contains") or str(exp["symptom_contains"]).casefold() in " ".join(case.get("symptoms") or []).casefold(),"scope_present":not exp.get("scope_contains") or str(exp["scope_contains"]).casefold() in str(case.get("affected_scope") or "").casefold(),"attempt_count":exp.get("attempt_count") is None or len(attempts)>=int(exp["attempt_count"]),"attempt_result_recorded":d.get("action")!="record_attempt_result" or bool(attempts and attempts[-1].get("result")),"troubleshooting_memory":d.get("intent")!="troubleshooting" or d.get("conversation_act") not in {"report_issue","request_next_step"} or bool(case.get("symptoms")),"turn_incremented":int(a.get("turn_number",0))==int(b.get("turn_number",0))+1,"answer_present":bool(answer.get("text")),"contextual_query_when_retrieval":not d.get("requires_retrieval") or bool(q.get("contextual_query")),"production_unchanged":True};failed=[k for k,v in checks.items() if not v];return {"checks":checks,"failed_checks":failed,"status":"passed" if not failed else "failed"}
def run_multiturn_scenario(scenario,secrets,session_state):
 start=time.perf_counter();g=LLMGateway(load_gateway_config(secrets),session_state);before=list(session_state.get("llm_gateway_history",[]) or []);state=ConversationState(conversation_id=str(scenario.get("id") or "multiturn"));turns=[];err=None
 try:
  route=AdaptiveCostRouteController(int(secrets.get("AGENT_CORE_V2_INITIAL_CANDIDATES",3)),int(secrets.get("AGENT_CORE_V2_MAX_CANDIDATES",6)));eng=TurnEngine(QwenInterpreter(g,int(secrets.get("LLM_ORCHESTRATOR_MAX_TOKENS",240))),SemanticEvidencePipeline(_ret,g,route.max_candidates,int(secrets.get("LLM_EVIDENCE_JUDGE_MAX_TOKENS",300))),ResponseComposer(g,int(secrets.get("LLM_ANSWER_MAX_TOKENS",400))),EntityResolver(),route);ex=scenario.get("turn_expectations") or []
  for i,m in enumerate(scenario.get("messages") or []):
   t=eng.process_turn(str(m),state).to_dict();t["production_changed"]=False;t["multiturn_checkpoint"]=_checkpoint(t,ex[i] if i<len(ex) else {});turns.append(t)
  status="ok"
 except Exception as x:status="error";err=f"{type(x).__name__}: {x}"
 nums=[(x.get("state_after") or {}).get("turn_number") for x in turns];checks={"all_turns_executed":len(turns)==len(scenario.get("messages") or []),"single_shared_conversation":len({(x.get("state_after") or {}).get("conversation_id") for x in turns})==1,"monotonic_turn_numbers":nums==list(range(1,len(turns)+1)),"all_turn_checkpoints_passed":all(x.get("multiturn_checkpoint",{}).get("status")=="passed" for x in turns),"no_production_change":all(not x.get("production_changed") for x in turns)};conversation={"checks":checks,"failed_checks":[k for k,v in checks.items() if not v],"status":"passed" if all(checks.values()) else "failed","scope":"isolated_multiturn_lab"};after=list(session_state.get("llm_gateway_history",[]) or [])
 return {"scenario_id":scenario.get("id"),"name":scenario.get("name"),"status":status,"error":err,"turns":turns,"final_state":state.to_dict(),"conversation_checkpoint":conversation,"usage":_usage(before,after),"latency_ms":round((time.perf_counter()-start)*1000,3),"latency_evaluated":False,"production_changed":False,"checkpoint_passed":conversation["status"]=="passed"}
