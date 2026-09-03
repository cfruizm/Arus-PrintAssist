from __future__ import annotations
import json
from .models import InterpreterProposal
from .semantic_delta import normalize_delta,validate_delta,proposal_payload
FUNCTIONS=["report_issue","add_case_facts","request_next_step","request_information","request_requirements","request_procedure","report_attempt","report_attempt_result","start_escalation","continue_escalation","suspend_escalation","resume_escalation","switch_topic","return_to_previous","cancel","out_of_scope","social","unknown"]
DELTA_SCHEMA={"type":"object","properties":{"turn_function":{"type":"string","enum":FUNCTIONS},"topic_relation":{"type":"string","enum":["same_topic","new_topic","independent_question","return_to_previous","unknown"]},"entities":{"type":"array","items":{"type":"object","properties":{"kind":{"type":"string","enum":["product","component","process"]},"canonical_id":{"type":"string"},"canonical_name":{"type":"string"},"matched_text":{"type":"string"},"confidence":{"type":"number"}},"required":["kind","canonical_name","matched_text"]}},"new_facts":{"type":"array","items":{"type":"object","properties":{"category":{"type":"string"},"value":{"type":"string"},"confidence":{"type":"number"},"correction":{"type":"boolean"}},"required":["category","value"]}},"user_requests_response":{"type":"boolean"},"user_requests_documentation":{"type":"boolean"},"confidence":{"type":"number"},"reasoning_summary":{"type":"string"}},"required":["turn_function","topic_relation","entities","new_facts","user_requests_response","user_requests_documentation","confidence","reasoning_summary"]}
def _extract(text):
 text=str(text or "").strip();a=text.find("{");b=text.rfind("}")
 if a<0 or b<a:raise ValueError("incomplete_json")
 return json.loads(text[a:b+1])
def _intent(state):return getattr(getattr(state,"active_topic",None),"intent",None)
def _fallback(state,reason):return InterpreterProposal(**proposal_payload(normalize_delta({"turn_function":"unknown","topic_relation":"same_topic" if getattr(getattr(state,"active_topic",None),"products",[]) else "unknown","entities":[],"new_facts":[],"confidence":.35,"reasoning_summary":"fallback:"+reason}),_intent(state)))
class QwenInterpreter:
 def __init__(self,gateway,max_tokens=240):self.gateway=gateway;self.max_tokens=max(240,min(340,int(max_tokens)))
 def _call(self,message,state,purpose,repair_issues=None):
  from app.llm_gateway.models import LLMRequest
  definitions={"report_issue":"A malfunction or unexpected behavior is reported. Must include a symptom fact. This is not an attempted action.","add_case_facts":"Only new context is added to an existing case. Must include at least one new fact.","request_next_step":"The user asks what to validate or do next for an active incident.","request_information":"The user asks for explanatory or conceptual information.","request_requirements":"The user asks for prerequisites, dependencies or requirements. This is not a procedure.","request_procedure":"The user asks how to perform an operation.","report_attempt":"The user states an action already performed. Must include attempted_action.","report_attempt_result":"The user states the outcome of the active attempt. Must include attempt_result.","switch_topic":"The user moves to a different subject without yet asking for one of the request functions."}
  instruction="Interpret the message as a semantic delta against canonical state. Use the function definitions exactly. Return only new facts, not copies from state. Never use report_attempt for a malfunction. Never use add_case_facts without new_facts. Fact objects must use category and value. Entity objects must use kind, canonical_name and matched_text. reasoning_summary maximum 10 words."
  payload={"message":message,"canonical_state":state.to_dict(),"function_definitions":definitions}
  if repair_issues:payload={"invalid_delta":message,"canonical_state":state.to_dict(),"contract_issues":repair_issues,"instruction":"Repair semantics and required facts. Do not copy existing state."}
  return self.gateway.complete(LLMRequest([{"role":"system","content":instruction},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],purpose,self.max_tokens,0.,DELTA_SCHEMA))
 def interpret(self,message,state):
  first=self._call(message,state,"agent_core_v2_semantic_delta")
  if not first.ok or first.finish_reason=="length":return _fallback(state,"provider_or_truncation")
  try:delta=normalize_delta(_extract(first.text))
  except Exception:return _fallback(state,"invalid_json")
  issues=validate_delta(delta,state)
  if issues:
   repair=self._call(first.text,state,"agent_core_v2_semantic_delta_repair",issues)
   if not repair.ok or repair.finish_reason=="length":return _fallback(state,"repair_failed")
   try:delta=normalize_delta(_extract(repair.text))
   except Exception:return _fallback(state,"repair_invalid")
   if validate_delta(delta,state):return _fallback(state,"repair_contract_failed")
  return InterpreterProposal(**proposal_payload(delta,_intent(state)))
class ScriptedInterpreter:
 def __init__(self,outputs):self.outputs=list(outputs);self.i=0
 def interpret(self,message,state):
  d=normalize_delta(self.outputs[self.i]);self.i+=1
  if validate_delta(d,state):return _fallback(state,"scripted_contract_failed")
  return InterpreterProposal(**proposal_payload(d,_intent(state)))
