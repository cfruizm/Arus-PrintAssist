from __future__ import annotations
from dataclasses import dataclass,field,asdict
from typing import Any

CONVERSATION_ACTS={"technical_request","case_update","attempt","attempt_result","capability","social","farewell","clarification","escalation","cancel","unknown"}
REQUEST_KINDS={"none","conceptual","procedural","troubleshooting","requirements","architecture","warranty"}
TOPIC_RELATIONS={"same_topic","new_topic","previous_topic","independent_question","unknown"}
FACT_CATEGORIES={"symptom","affected_scope","timeline","change_context","environment","error_message","version","location","frequency","observed_behavior","expected_behavior","attempted_action","attempt_result","technical_context"}
ENTITY_KINDS={"product","component","process"}

@dataclass
class CurrentRequest:
 conversation_act:str="unknown"
 request_kind:str="none"
 topic_relation:str="unknown"
 entities:list[dict[str,Any]]=field(default_factory=list)
 new_facts:list[dict[str,Any]]=field(default_factory=list)
 needs_documents:bool=False
 escalation_action:str="none"
 confidence:float=0.0
 reasoning_summary:str=""
 ignored_fields:list[str]=field(default_factory=list)
 def to_dict(self):return asdict(self)

def _value(item,*keys):
 for key in keys:
  if item.get(key) not in (None,""):return item.get(key)
 return None

def normalize_current_request(raw):
 raw=dict(raw or {});allowed={"conversation_act","request_kind","topic_relation","entities","new_facts","needs_documents","escalation_action","confidence","reasoning_summary"};ignored=sorted(set(raw)-allowed)
 act=str(raw.get("conversation_act") or "unknown");kind=str(raw.get("request_kind") or "none");relation=str(raw.get("topic_relation") or "unknown")
 if act not in CONVERSATION_ACTS:act="unknown"
 if kind not in REQUEST_KINDS:kind="none"
 if relation not in TOPIC_RELATIONS:relation="unknown"
 entities=[]
 for source in raw.get("entities") or []:
  if not isinstance(source,dict):continue
  entity_kind=str(_value(source,"kind","type") or "");name=str(_value(source,"canonical_name","name","canonical","mention","matched_text") or "").strip()
  if entity_kind in ENTITY_KINDS and name:entities.append({"kind":entity_kind,"canonical_id":str(_value(source,"canonical_id","id") or ""),"canonical_name":name,"matched_text":str(_value(source,"matched_text","mention") or name),"confidence":float(source.get("confidence",raw.get("confidence",0)) or 0)})
 facts=[]
 aliases={"scope":"affected_scope","impact":"affected_scope","action":"attempted_action","attempt":"attempted_action","result":"attempt_result","status":"change_context"}
 for source in raw.get("new_facts") or []:
  if not isinstance(source,dict):continue
  category=str(_value(source,"category","type","key") or "technical_context");category=aliases.get(category,category);value=str(_value(source,"value","fact","name") or "").strip()
  if category in FACT_CATEGORIES and value:facts.append({"type":category,"value":value,"confidence":float(source.get("confidence",raw.get("confidence",0)) or 0),"correction":bool(source.get("correction",False)),"source":"current_request"})
 return CurrentRequest(act,kind,relation,entities,facts,bool(raw.get("needs_documents",False)),str(raw.get("escalation_action") or "none"),float(raw.get("confidence",0) or 0),str(raw.get("reasoning_summary") or "")[:140],ignored)

def validate_current_request(req,state):
 issues=[];categories={x["type"] for x in req.new_facts};active_attempts=getattr(getattr(state,"technical_case",None),"attempts",[]) or []
 if req.conversation_act=="attempt" and "attempted_action" not in categories:issues.append("attempt_requires_action")
 if req.conversation_act=="attempt_result" and "attempt_result" not in categories:issues.append("attempt_result_requires_result")
 if req.conversation_act=="attempt_result" and not active_attempts:issues.append("attempt_result_requires_active_attempt")
 if req.conversation_act=="case_update" and not req.new_facts:issues.append("case_update_requires_delta")
 if req.conversation_act=="technical_request" and req.request_kind=="none":issues.append("technical_request_requires_kind")
 if req.conversation_act in {"capability","social","farewell","cancel"} and req.needs_documents:issues.append("nontechnical_act_must_not_retrieve")
 return issues

def to_proposal(req,active_intent=None):
 action="respond_directly";intent=req.request_kind if req.request_kind!="none" else (active_intent or "unknown");clarification=None
 if req.conversation_act=="technical_request":action="retrieve" if req.needs_documents else "respond_directly"
 elif req.conversation_act=="case_update":action="record_case_detail"
 elif req.conversation_act=="attempt":action="record_attempt";intent="troubleshooting"
 elif req.conversation_act=="attempt_result":action="record_attempt_result";intent="troubleshooting"
 elif req.conversation_act=="capability":intent="capabilities"
 elif req.conversation_act in {"social","farewell"}:intent="social"
 elif req.conversation_act=="escalation":intent="escalation";action="start_escalation" if req.escalation_action=="start" else "continue_escalation"
 elif req.conversation_act=="cancel":intent="cancel";action="cancel_all"
 elif req.conversation_act in {"clarification","unknown"}:action="ask_clarification";clarification="No estoy seguro de haber entendido la solicitud. ¿Puedes aclarar qué necesitas respecto al caso actual?"
 return {"conversation_act":req.conversation_act,"intent":intent,"requested_action":action,"topic_relation":req.topic_relation,"entities":req.entities,"facts":req.new_facts,"clarification_question":clarification,"confidence":req.confidence,"reasoning_summary":req.reasoning_summary}
