from __future__ import annotations
from dataclasses import dataclass,field,asdict
from typing import Any
TURN_FUNCTIONS={"report_issue","add_case_facts","request_next_step","request_information","request_requirements","request_procedure","report_attempt","report_attempt_result","start_escalation","continue_escalation","suspend_escalation","resume_escalation","switch_topic","return_to_previous","cancel","out_of_scope","social","unknown"}
FACT_CATEGORIES={"symptom","affected_scope","timeline","change_context","environment","error_message","version","location","frequency","reproducibility","observed_behavior","expected_behavior","attempted_action","attempt_result","technical_context"}
ENTITY_KINDS={"product","component","process"}
@dataclass
class SemanticFact: category:str;value:str;confidence:float=.0;correction:bool=False
@dataclass
class SemanticTurnDelta:
 turn_function:str="unknown";topic_relation:str="unknown";entities:list[dict[str,Any]]=field(default_factory=list);new_facts:list[SemanticFact]=field(default_factory=list);user_requests_response:bool=True;user_requests_documentation:bool=False;confidence:float=.0;reasoning_summary:str="";ignored_fields:list[str]=field(default_factory=list)
 def to_dict(self):return asdict(self)
def _first(item,*keys,default=""):
 for key in keys:
  if key in item and item[key] not in (None,""):return item[key]
 return default
def normalize_delta(raw):
 raw=dict(raw or {});allowed={"turn_function","topic_relation","entities","new_facts","user_requests_response","user_requests_documentation","confidence","reasoning_summary"};ignored=sorted(set(raw)-allowed);function=str(raw.get("turn_function") or "unknown");relation=str(raw.get("topic_relation") or "unknown")
 if function not in TURN_FUNCTIONS:function="unknown"
 if relation not in {"same_topic","new_topic","independent_question","return_to_previous","unknown"}:relation="unknown"
 entities=[]
 for source in raw.get("entities") or []:
  if not isinstance(source,dict):continue
  kind=str(_first(source,"kind","type"));name=str(_first(source,"canonical_name","canonical","name","matched_text","mention")).strip();matched=str(_first(source,"matched_text","mention",default=name)).strip()
  if kind in ENTITY_KINDS and name:entities.append({"kind":kind,"canonical_id":str(source.get("canonical_id") or ""),"canonical_name":name,"matched_text":matched or name,"confidence":float(source.get("confidence",raw.get("confidence",0)) or 0)})
 facts=[]
 aliases={"scope":"affected_scope","impact":"affected_scope","state":"change_context","status":"change_context","action":"attempted_action","result":"attempt_result"}
 for source in raw.get("new_facts") or []:
  if not isinstance(source,dict):continue
  category=str(_first(source,"category","type","kind",default="technical_context"));category=aliases.get(category,category);value=str(_first(source,"value","fact","description","name")).strip()
  if category in FACT_CATEGORIES and value:facts.append(SemanticFact(category,value,float(source.get("confidence",raw.get("confidence",0)) or 0),bool(source.get("correction",False))))
 return SemanticTurnDelta(function,relation,entities,facts,bool(raw.get("user_requests_response",True)),bool(raw.get("user_requests_documentation",False)),float(raw.get("confidence",0) or 0),str(raw.get("reasoning_summary") or "")[:120],ignored)
def validate_delta(delta,state):
 categories={x.category for x in delta.new_facts};issues=[];case=getattr(state,"technical_case",None);has_active=bool(getattr(getattr(state,"active_topic",None),"products",[]) or getattr(case,"symptoms",[]));has_attempt=bool(getattr(case,"attempts",[]))
 required={"report_issue":{"symptom"},"report_attempt":{"attempted_action"},"report_attempt_result":{"attempt_result"}}
 missing=required.get(delta.turn_function,set())-categories
 if missing:issues.append("missing_required_facts:"+",".join(sorted(missing)))
 if delta.turn_function=="report_attempt_result" and not has_attempt:issues.append("attempt_result_without_active_attempt")
 if delta.turn_function=="add_case_facts" and not delta.new_facts:issues.append("case_update_without_new_facts")
 if delta.turn_function in {"request_next_step","report_attempt","report_attempt_result"} and not has_active:issues.append("active_case_required")
 return issues
ROUTES={"report_issue":("report_issue","troubleshooting","retrieve"),"add_case_facts":("provide_case_detail","troubleshooting","record_case_detail"),"request_next_step":("request_next_step","troubleshooting","retrieve"),"request_information":("request_information","conceptual","retrieve"),"request_requirements":("request_requirements","requirements","retrieve"),"request_procedure":("request_procedure","procedural","retrieve"),"report_attempt":("report_attempt","troubleshooting","record_attempt"),"report_attempt_result":("report_attempt_result","troubleshooting","record_attempt_result"),"start_escalation":("start_escalation","escalation","start_escalation"),"continue_escalation":("continue_escalation","escalation","continue_escalation"),"suspend_escalation":("suspend_escalation","escalation","suspend_escalation"),"resume_escalation":("resume_escalation","resume","resume_escalation"),"switch_topic":("switch_topic","unknown","respond_directly"),"return_to_previous":("return_to_previous","unknown","respond_directly"),"cancel":("cancel_all","cancel","cancel_all"),"out_of_scope":("out_of_scope","out_of_scope","out_of_scope"),"social":("social","social","respond_directly"),"unknown":("clarify","unknown","ask_clarification")}
def proposal_payload(delta,active_intent=None):
 act,intent,action=ROUTES[delta.turn_function]
 if intent=="unknown":intent=active_intent or "unknown"
 facts=[{"type":x.category,"value":x.value,"confidence":x.confidence,"correction":x.correction,"source":"semantic_delta"} for x in delta.new_facts]
 return {"conversation_act":act,"intent":intent,"requested_action":action,"topic_relation":"same_topic" if delta.topic_relation=="return_to_previous" else delta.topic_relation,"entities":delta.entities,"facts":facts,"clarification_question":"Necesito una precisión adicional para continuar." if delta.turn_function=="unknown" else None,"confidence":delta.confidence,"reasoning_summary":delta.reasoning_summary}
