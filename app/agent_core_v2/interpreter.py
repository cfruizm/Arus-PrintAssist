from __future__ import annotations
import json,re
from .models import InterpreterProposal

ALLOWED_INTENTS={"social","capabilities","support_intake","conceptual","procedural","troubleshooting","requirements","architecture","warranty","escalation","cancel","resume","out_of_scope","unknown"}
ALLOWED_ACTIONS={"respond_directly","ask_clarification","retrieve","record_case_detail","record_attempt","record_attempt_result","start_escalation","continue_escalation","suspend_escalation","resume_escalation","cancel_all","out_of_scope"}
ALLOWED_RELATIONS={"same_topic","new_topic","independent_question","unknown"}
SCHEMA={"type":"object","properties":{
 "conversation_act":{"type":"string"},"intent":{"type":"string","enum":sorted(ALLOWED_INTENTS)},"requested_action":{"type":"string","enum":sorted(ALLOWED_ACTIONS)},"topic_relation":{"type":"string","enum":sorted(ALLOWED_RELATIONS)},"entities":{"type":"array","items":{"type":"object","properties":{"kind":{"type":"string"},"canonical_id":{"type":"string"},"canonical_name":{"type":"string"},"matched_text":{"type":"string"},"confidence":{"type":"number"}},"required":["kind","canonical_name"]}},"facts":{"type":"array","items":{"type":"object","properties":{"type":{"type":"string"},"value":{"type":"string"},"confidence":{"type":"number"}},"required":["type","value"]}},"clarification_question":{"type":["string","null"]},"confidence":{"type":"number"},"reasoning_summary":{"type":"string"}},
 "required":["conversation_act","intent","requested_action","topic_relation","entities","facts","clarification_question","confidence","reasoning_summary"]}

INTENT_ALIASES={"troubleshoot_access":"troubleshooting","troubleshoot":"troubleshooting","procedure":"procedural","concept":"conceptual"}
RELATION_ALIASES={"related":"same_topic","same":"same_topic","new":"new_topic"}

def _extract(text):
 text=str(text or "").strip();start=text.find("{");end=text.rfind("}")
 if start<0 or end<start:raise ValueError("The model did not return a complete JSON object")
 return json.loads(text[start:end+1])
def _id(value):return re.sub(r"[^a-z0-9]+","_",str(value).casefold()).strip("_")
def normalize_payload(raw):
 raw=dict(raw or {});raw["intent"]=INTENT_ALIASES.get(str(raw.get("intent") or ""),str(raw.get("intent") or "unknown"));raw["topic_relation"]=RELATION_ALIASES.get(str(raw.get("topic_relation") or ""),str(raw.get("topic_relation") or "unknown"))
 if raw["intent"] not in ALLOWED_INTENTS:raw["intent"]="unknown"
 if raw.get("requested_action") not in ALLOWED_ACTIONS:raw["requested_action"]="ask_clarification"
 if raw["topic_relation"] not in ALLOWED_RELATIONS:raw["topic_relation"]="unknown"
 entities=[]
 for x in raw.get("entities") or []:
  if not isinstance(x,dict):continue
  name=str(x.get("canonical_name") or x.get("name") or x.get("value") or "").strip()
  if name:entities.append({"kind":str(x.get("kind") or x.get("type") or "product"),"canonical_id":str(x.get("canonical_id") or x.get("id") or _id(name)),"canonical_name":name,"matched_text":str(x.get("matched_text") or name),"confidence":float(x.get("confidence",raw.get("confidence",.7)))})
 raw["entities"]=entities
 facts=[]
 for x in raw.get("facts") or []:
  if isinstance(x,str):facts.append({"type":"symptom","value":x,"confidence":float(raw.get("confidence",.7))})
  elif isinstance(x,dict) and str(x.get("value") or "").strip():facts.append({"type":str(x.get("type") or "technical_context"),"value":str(x.get("value")),"confidence":float(x.get("confidence",raw.get("confidence",.7)))})
 raw["facts"]=facts;raw["conversation_act"]=str(raw.get("conversation_act") or "unknown");raw["clarification_question"]=raw.get("clarification_question");raw["confidence"]=float(raw.get("confidence",0));raw["reasoning_summary"]=str(raw.get("reasoning_summary") or "")[:160]
 return raw

class QwenInterpreter:
 def __init__(self,gateway,max_tokens=220):self.gateway=gateway;self.max_tokens=max(240,min(320,int(max_tokens)))
 def interpret(self,message,state):
  from app.llm_gateway.models import LLMRequest
  system="""Classify one printing-support turn. Return compact JSON only. Use only enum values from the schema. entities and facts must be objects. reasoning_summary max 12 words. If the message already asks what to validate and names a product plus symptom, use intent troubleshooting and requested_action retrieve. Do not answer the technical question."""
  payload=json.dumps({"message":message,"state":state.to_dict()},ensure_ascii=False,separators=(",",":"))
  result=self.gateway.complete(LLMRequest([{"role":"system","content":system},{"role":"user","content":payload}],"agent_core_v2_interpreter",self.max_tokens,0.,SCHEMA))
  if not result.ok:raise RuntimeError(result.error_message or "interpreter_provider_failed")
  if result.finish_reason=="length":raise ValueError(f"Interpreter output was truncated at {result.usage.get('completion_tokens',self.max_tokens)} tokens")
  return InterpreterProposal(**normalize_payload(_extract(result.text)))
class ScriptedInterpreter:
 def __init__(self,outputs):self.outputs=list(outputs);self.i=0
 def interpret(self,message,state):r=self.outputs[self.i];self.i+=1;return InterpreterProposal(**normalize_payload(r))
