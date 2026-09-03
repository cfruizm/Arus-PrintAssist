from __future__ import annotations
from dataclasses import dataclass,field,asdict
from typing import Any

TURN_FUNCTIONS={
 "add_case_facts","request_next_step","request_information","request_procedure",
 "report_attempt","report_attempt_result","start_escalation","continue_escalation",
 "suspend_escalation","resume_escalation","switch_topic","cancel","out_of_scope",
 "social","unknown"
}
FACT_CATEGORIES={
 "symptom","affected_scope","timeline","change_context","environment","error_message",
 "version","location","frequency","reproducibility","observed_behavior","expected_behavior",
 "attempted_action","attempt_result","technical_context"
}
ENTITY_KINDS={"product","component","process"}

@dataclass
class SemanticFact:
 category:str
 value:str
 confidence:float=.0
 correction:bool=False

@dataclass
class SemanticTurnDelta:
 turn_function:str="unknown"
 topic_relation:str="unknown"
 entities:list[dict[str,Any]]=field(default_factory=list)
 new_facts:list[SemanticFact]=field(default_factory=list)
 user_requests_response:bool=True
 user_requests_documentation:bool=False
 confidence:float=.0
 reasoning_summary:str=""
 ignored_fields:list[str]=field(default_factory=list)
 def to_dict(self):return asdict(self)

def normalize_delta(raw:dict[str,Any]|None)->SemanticTurnDelta:
 raw=dict(raw or {});ignored=sorted(set(raw)-{"turn_function","topic_relation","entities","new_facts","user_requests_response","user_requests_documentation","confidence","reasoning_summary"})
 function=str(raw.get("turn_function") or "unknown")
 if function not in TURN_FUNCTIONS:function="unknown"
 relation=str(raw.get("topic_relation") or "unknown")
 if relation not in {"same_topic","new_topic","independent_question","return_to_previous","unknown"}:relation="unknown"
 entities=[]
 for item in raw.get("entities") or []:
  if not isinstance(item,dict):continue
  kind=str(item.get("kind") or "")
  name=str(item.get("canonical_name") or item.get("name") or item.get("matched_text") or "").strip()
  if kind in ENTITY_KINDS and name:
   entities.append({"kind":kind,"canonical_id":str(item.get("canonical_id") or "").strip(),"canonical_name":name,"matched_text":str(item.get("matched_text") or name),"confidence":float(item.get("confidence",raw.get("confidence",0)) or 0)})
 facts=[]
 for item in raw.get("new_facts") or []:
  if not isinstance(item,dict):continue
  category=str(item.get("category") or "technical_context")
  value=str(item.get("value") or "").strip()
  if category in FACT_CATEGORIES and value:facts.append(SemanticFact(category,value,float(item.get("confidence",raw.get("confidence",0)) or 0),bool(item.get("correction",False))))
 return SemanticTurnDelta(function,relation,entities,facts,bool(raw.get("user_requests_response",True)),bool(raw.get("user_requests_documentation",False)),float(raw.get("confidence",0) or 0),str(raw.get("reasoning_summary") or "")[:120],ignored)

ROUTE_MAP={
 "add_case_facts":("provide_case_detail","record_case_detail"),
 "request_next_step":("request_next_step","retrieve"),
 "request_information":("request_information","retrieve"),
 "request_procedure":("request_procedure","retrieve"),
 "report_attempt":("report_attempt","record_attempt"),
 "report_attempt_result":("report_attempt_result","record_attempt_result"),
 "start_escalation":("start_escalation","start_escalation"),
 "continue_escalation":("continue_escalation","continue_escalation"),
 "suspend_escalation":("suspend_escalation","suspend_escalation"),
 "resume_escalation":("resume_escalation","resume_escalation"),
 "switch_topic":("switch_topic","respond_directly"),
 "cancel":("cancel_all","cancel_all"),
 "out_of_scope":("out_of_scope","out_of_scope"),
 "social":("social","respond_directly"),
 "unknown":("clarify","ask_clarification"),
}
INTENT_MAP={
 "request_procedure":"procedural","request_next_step":"troubleshooting",
 "report_attempt":"troubleshooting","report_attempt_result":"troubleshooting",
 "add_case_facts":"troubleshooting","start_escalation":"escalation",
 "continue_escalation":"escalation","resume_escalation":"resume",
 "cancel":"cancel","out_of_scope":"out_of_scope","social":"social"
}

def proposal_payload(delta:SemanticTurnDelta,active_intent:str|None=None)->dict[str,Any]:
 act,action=ROUTE_MAP[delta.turn_function]
 intent=INTENT_MAP.get(delta.turn_function,active_intent or "unknown")
 if delta.turn_function=="request_information" and intent=="unknown":intent="conceptual"
 facts=[{"type":x.category,"value":x.value,"confidence":x.confidence,"correction":x.correction,"source":"semantic_delta"} for x in delta.new_facts]
 clarification=None if delta.turn_function!="unknown" else "Necesito una precisión adicional para continuar."
 return {"conversation_act":act,"intent":intent,"requested_action":action,"topic_relation":"same_topic" if delta.topic_relation=="return_to_previous" else delta.topic_relation,"entities":delta.entities,"facts":facts,"clarification_question":clarification,"confidence":delta.confidence,"reasoning_summary":delta.reasoning_summary}
