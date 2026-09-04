from __future__ import annotations
import json
from .models import InterpreterProposal
from .semantic_delta import normalize_delta,validate_delta,proposal_payload
FUNCTIONS=["report_issue","add_case_facts","request_next_step","request_information","request_requirements","request_procedure","report_attempt","report_attempt_result","start_escalation","continue_escalation","suspend_escalation","resume_escalation","switch_topic","return_to_previous","cancel","out_of_scope","social","unknown"]
DELTA_SCHEMA={"type":"object","properties":{"turn_function":{"type":"string","enum":FUNCTIONS},"topic_relation":{"type":"string"},"entities":{"type":"array","items":{"type":"object"}},"new_facts":{"type":"array","items":{"type":"object"}},"user_requests_response":{"type":"boolean"},"user_requests_documentation":{"type":"boolean"},"confidence":{"type":"number"},"reasoning_summary":{"type":"string"}},"required":["turn_function","topic_relation","entities","new_facts","user_requests_response","user_requests_documentation","confidence","reasoning_summary"]}
def _extract(text):
 text=str(text or "").strip();a=text.find("{");b=text.rfind("}")
 if a<0 or b<a:raise ValueError("incomplete_json")
 return json.loads(text[a:b+1])
def _intent(state):return getattr(getattr(state,"active_topic",None),"intent",None)
def _fallback(state,reason):return InterpreterProposal(**proposal_payload(normalize_delta({"turn_function":"unknown","topic_relation":"same_topic" if getattr(getattr(state,"active_topic",None),"products",[]) else "unknown","entities":[],"new_facts":[],"confidence":.35,"reasoning_summary":"fallback:"+reason}),_intent(state)))
class QwenInterpreter:
 def __init__(self,gateway,max_tokens=240):self.gateway=gateway;self.max_tokens=max(240,min(340,int(max_tokens)));self.last_trace={}
 def _complete(self,payload,purpose):
  from app.llm_gateway.models import LLMRequest
  system="""Interpret the original user message as a semantic delta against canonical state. Distinguish: report_issue is a malfunction and requires symptom; report_attempt is an action the user performed and requires attempted_action; report_attempt_result is the outcome of an already registered attempt and requires attempt_result; request_requirements asks for prerequisites or dependencies and is not a procedure. Return only genuinely new facts. Use category/value for facts and kind/canonical_name/matched_text for entities. Never infer from product names or benchmark phrases. reasoning_summary maximum 10 words."""
  return self.gateway.complete(LLMRequest([{"role":"system","content":system},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],purpose,self.max_tokens,0.,DELTA_SCHEMA))
 def interpret(self,message,state):
  self.last_trace={"original_message":message,"repair_used":False,"initial_function":None,"violations":[],"repaired_function":None,"repair_valid":None}
  first=self._complete({"original_user_message":message,"canonical_state":state.to_dict(),"task":"Interpret the original message."},"agent_core_v2_semantic_delta")
  if not first.ok or first.finish_reason=="length":return _fallback(state,"provider_or_truncation")
  try:delta=normalize_delta(_extract(first.text))
  except Exception:return _fallback(state,"invalid_json")
  issues=validate_delta(delta,state);self.last_trace["initial_function"]=delta.turn_function;self.last_trace["violations"]=issues
  if issues:
   self.last_trace["repair_used"]=True
   payload={"original_user_message":message,"invalid_delta":delta.to_dict(),"canonical_state":state.to_dict(),"contract_violations":issues,"repair_objective":"Reinterpret the ORIGINAL USER MESSAGE. The invalid delta is evidence of what to correct, not the source text. Preserve the user's action or outcome in the required fact. If no prior attempt exists, report_attempt_result is impossible; decide whether the original message reports an action performed or another function."}
   repaired=self._complete(payload,"agent_core_v2_semantic_delta_repair")
   if not repaired.ok or repaired.finish_reason=="length":return _fallback(state,"repair_failed")
   try:delta=normalize_delta(_extract(repaired.text))
   except Exception:return _fallback(state,"repair_invalid")
   remaining=validate_delta(delta,state);self.last_trace["repaired_function"]=delta.turn_function;self.last_trace["repair_valid"]=not remaining
   if remaining:return _fallback(state,"repair_contract_failed")
  return InterpreterProposal(**proposal_payload(delta,_intent(state)))
class ScriptedInterpreter:
 def __init__(self,outputs):self.outputs=list(outputs);self.i=0;self.last_trace={}
 def interpret(self,message,state):
  delta=normalize_delta(self.outputs[self.i]);self.i+=1;issues=validate_delta(delta,state);self.last_trace={"original_message":message,"repair_used":False,"initial_function":delta.turn_function,"violations":issues,"repair_valid":not issues}
  return _fallback(state,"scripted_contract_failed") if issues else InterpreterProposal(**proposal_payload(delta,_intent(state)))
