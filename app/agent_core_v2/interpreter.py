from __future__ import annotations
import json
from .models import InterpreterProposal
from .semantic_delta import normalize_delta,proposal_payload

DELTA_SCHEMA={"type":"object","properties":{
 "turn_function":{"type":"string","enum":["add_case_facts","request_next_step","request_information","request_procedure","report_attempt","report_attempt_result","start_escalation","continue_escalation","suspend_escalation","resume_escalation","switch_topic","cancel","out_of_scope","social","unknown"]},
 "topic_relation":{"type":"string","enum":["same_topic","new_topic","independent_question","return_to_previous","unknown"]},
 "entities":{"type":"array","items":{"type":"object"}},
 "new_facts":{"type":"array","items":{"type":"object"}},
 "user_requests_response":{"type":"boolean"},"user_requests_documentation":{"type":"boolean"},
 "confidence":{"type":"number"},"reasoning_summary":{"type":"string"}},
 "required":["turn_function","topic_relation","entities","new_facts","user_requests_response","user_requests_documentation","confidence","reasoning_summary"]}

def _extract(text):
 text=str(text or "").strip();a=text.find("{");b=text.rfind("}")
 if a<0 or b<a:raise ValueError("incomplete_delta_json")
 return json.loads(text[a:b+1])
def _active_intent(state):
 try:return state.active_topic.intent
 except Exception:return None

def safe_fallback(state,reason):
 payload={"turn_function":"unknown","topic_relation":"same_topic" if getattr(getattr(state,"active_topic",None),"products",[]) else "unknown","entities":[],"new_facts":[],"user_requests_response":True,"user_requests_documentation":False,"confidence":.4,"reasoning_summary":f"fallback:{reason}"}
 return InterpreterProposal(**proposal_payload(normalize_delta(payload),_active_intent(state)))

class QwenInterpreter:
 def __init__(self,gateway,max_tokens=220):self.gateway=gateway;self.max_tokens=max(220,min(300,int(max_tokens)))
 def interpret(self,message,state):
  from app.llm_gateway.models import LLMRequest
  system="""Interpret the current support message as a semantic delta against the canonical state. Do not classify by keyword matching and do not repeat facts or entities already stored unless the user corrects them. Select one turn_function based on communicative purpose. add_case_facts means the user only contributes new case information and does not request a technical answer. request_next_step means the user asks what to validate or do next for the active unresolved case. request_procedure means the user asks how to perform an operation, without reporting a malfunction. Put only genuinely new facts in new_facts. Generic affected objects are facts, not components. Return compact JSON only."""
  payload=json.dumps({"message":message,"canonical_state":state.to_dict()},ensure_ascii=False,separators=(",",":"));result=self.gateway.complete(LLMRequest([{"role":"system","content":system},{"role":"user","content":payload}],"agent_core_v2_semantic_delta",self.max_tokens,0.,DELTA_SCHEMA))
  if not result.ok:return safe_fallback(state,"provider_error")
  if result.finish_reason=="length":return safe_fallback(state,"truncated")
  try:
   delta=normalize_delta(_extract(result.text));return InterpreterProposal(**proposal_payload(delta,_active_intent(state)))
  except Exception:return safe_fallback(state,"invalid_output")

class ScriptedInterpreter:
 def __init__(self,outputs):self.outputs=list(outputs);self.index=0
 def interpret(self,message,state):
  raw=self.outputs[self.index];self.index+=1;return InterpreterProposal(**proposal_payload(normalize_delta(raw),_active_intent(state)))
