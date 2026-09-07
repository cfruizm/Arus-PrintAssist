from __future__ import annotations
import json
from .models import InterpreterProposal
from .semantic_delta import normalize_current_request,validate_current_request,to_proposal

SCHEMA={"type":"object","properties":{"conversation_act":{"type":"string","enum":["technical_request","case_update","attempt","attempt_result","capability","social","farewell","clarification","escalation","cancel","unknown"]},"request_kind":{"type":"string","enum":["none","conceptual","procedural","troubleshooting","requirements","architecture","warranty"]},"topic_relation":{"type":"string","enum":["same_topic","new_topic","previous_topic","independent_question","unknown"]},"entities":{"type":"array","items":{"type":"object"}},"new_facts":{"type":"array","items":{"type":"object"}},"needs_documents":{"type":"boolean"},"escalation_action":{"type":"string"},"confidence":{"type":"number"},"reasoning_summary":{"type":"string"}},"required":["conversation_act","request_kind","topic_relation","entities","new_facts","needs_documents","escalation_action","confidence","reasoning_summary"]}

def _json(text):
 text=str(text or "").strip();a=text.find("{");b=text.rfind("}")
 if a<0 or b<a:raise ValueError("incomplete_json")
 return json.loads(text[a:b+1])
def _active_intent(state):return getattr(getattr(state,"active_topic",None),"intent",None)
def _fallback(state,reason):
 req=normalize_current_request({"conversation_act":"clarification","request_kind":"none","topic_relation":"same_topic" if getattr(getattr(state,"active_topic",None),"products",[]) else "unknown","entities":[],"new_facts":[],"needs_documents":False,"escalation_action":"none","confidence":.35,"reasoning_summary":"fallback:"+reason});return InterpreterProposal(**to_proposal(req,_active_intent(state)))

class QwenInterpreter:
 def __init__(self,gateway,max_tokens=260):self.gateway=gateway;self.max_tokens=max(240,min(320,int(max_tokens)))
 def interpret(self,message,state):
  from app.llm_gateway.models import LLMRequest
  system="""Interpret the CURRENT message independently from the previous request type while using state for references and omitted entities. Preserve products and case facts, but recalculate what the user wants now. conversation_act is social function; request_kind is current technical need. A definition or purpose question is conceptual. A request for steps is procedural. Prerequisites are requirements. A malfunction or next diagnostic action is troubleshooting. Questions about the assistant are capability and require no documents. Greetings or farewells are social/farewell and require no documents. Extract only new facts. Do not force a technical request when the message is social. Return compact JSON only."""
  payload={"current_message":message,"canonical_state":state.to_dict(),"rule":"Current request overrides historical intent; historical intent is context only."};res=self.gateway.complete(LLMRequest([{"role":"system","content":system},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_current_request",self.max_tokens,0.,SCHEMA))
  if not res.ok or res.finish_reason=="length":return _fallback(state,"provider_or_truncation")
  try:req=normalize_current_request(_json(res.text))
  except Exception:return _fallback(state,"invalid_json")
  if validate_current_request(req,state):return _fallback(state,"contract_invalid")
  return InterpreterProposal(**to_proposal(req,_active_intent(state)))
class ScriptedInterpreter:
 def __init__(self,outputs):self.outputs=list(outputs);self.i=0
 def interpret(self,message,state):
  req=normalize_current_request(self.outputs[self.i]);self.i+=1
  return _fallback(state,"contract_invalid") if validate_current_request(req,state) else InterpreterProposal(**to_proposal(req,_active_intent(state)))
