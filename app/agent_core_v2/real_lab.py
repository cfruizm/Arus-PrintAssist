from __future__ import annotations
import time
from app.agent_core_v2.models import ConversationState
from app.agent_core_v2.interpreter import QwenInterpreter
from app.agent_core_v2.entity_resolver import EntityResolver
from app.agent_core_v2.evidence import EvidenceEngine
from app.agent_core_v2.response import ResponseComposer
from app.agent_core_v2.engine import TurnEngine
from app.integration.lab_retrieval_adapter import retrieve_from_existing_backend
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway
def _ret(q,n):
 r=retrieve_from_existing_backend(q,n);return list(r.get("evidence") or []) if isinstance(r,dict) and r.get("ok") else []
def _usage(b,a):
 f=a[len(b):] if len(a)>=len(b) else a;return {"calls":len(f),"prompt_tokens":sum(int(x.get("usage",{}).get("prompt_tokens",0) or 0) for x in f),"completion_tokens":sum(int(x.get("usage",{}).get("completion_tokens",0) or 0) for x in f),"total_tokens":sum(int(x.get("usage",{}).get("total_tokens",0) or 0) for x in f),"records":f}
def _grade(t,s):
 d=t.get("decision") or {};e=t.get("evidence") or {};a=t.get("answer") or {};st=t.get("state_after") or {};exp=s.get("expected") or {};products=[x.get("canonical_id") for x in st.get("active_topic",{}).get("products",[])];symptoms=st.get("technical_case",{}).get("symptoms",[]);citables=e.get("citable",[]);text=str(a.get("text") or "");modes={"truncated_fallback","invalid_citations","missing_citations"}
 checks={"intent":not exp.get("intent") or d.get("intent")==exp.get("intent"),"action":not exp.get("action") or d.get("action")==exp.get("action"),"entity":not exp.get("product_id") or exp.get("product_id") in products,"single_specific_product":len(products)<=1,"symptom_only_for_troubleshooting":d.get("intent")=="troubleshooting" or not symptoms,"symptom_captured":d.get("intent")!="troubleshooting" or bool(symptoms),"citation_integrity":set(a.get("citations") or []).issubset({x.get("id") for x in citables}),"citable_has_no_rejection_reasons":all(not x.get("rejection_reasons") for x in citables),"response_not_truncated":a.get("mode") not in modes and a.get("finish_reason")!="length","answer_present":d.get("action")!="retrieve" or bool(text),"procedural_hybrid_is_non_prescriptive":not (d.get("intent")=="procedural" and a.get("mode")=="hybrid_general") or not any(x in text.casefold() for x in ["navegar a","seleccionar el usuario","configurar el método","normalmente se realiza"])}
 failed=[k for k,v in checks.items() if not v];base="failed" if failed else "passed";status="partial" if base=="passed" and d.get("action")=="retrieve" and not citables else base
 return {"checks":checks,"failed_checks":failed,"status":status,"latency_evaluated":False,"scope":"real_lab_not_production"}
def run_real_scenario(scenario,secrets,session_state):
 start=time.perf_counter();g=LLMGateway(load_gateway_config(secrets),session_state);before=list(session_state.get("llm_gateway_history",[]) or []);state=ConversationState(conversation_id=str(scenario.get("id") or "lab"));turns=[];err=None
 try:
  eng=TurnEngine(QwenInterpreter(g,int(secrets.get("LLM_ORCHESTRATOR_MAX_TOKENS",220))),EvidenceEngine(_ret),ResponseComposer(g,int(secrets.get("LLM_ANSWER_MAX_TOKENS",400))),EntityResolver())
  for m in scenario.get("messages") or []:
   t=eng.process_turn(str(m),state).to_dict();t["functional_checkpoint"]=_grade(t,scenario);turns.append(t)
  status="ok"
 except Exception as x:status="error";err=f"{type(x).__name__}: {x}"
 after=list(session_state.get("llm_gateway_history",[]) or []);grades=[x.get("functional_checkpoint",{}).get("status") for x in turns];overall="failed" if status=="error" or "failed" in grades else "partial" if "partial" in grades else "passed"
 return {"scenario_id":scenario.get("id"),"name":scenario.get("name"),"status":status,"error":err,"turns":turns,"final_state":state.to_dict(),"usage":_usage(before,after),"latency_ms":round((time.perf_counter()-start)*1000,3),"latency_evaluated":False,"production_changed":False,"functional_result":overall,"checkpoint_passed":overall=="passed"}
