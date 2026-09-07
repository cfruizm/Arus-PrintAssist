from __future__ import annotations
import json
from .models import InterpreterProposal

ACTS={"technical_request","case_update","attempt","attempt_result","capability","social","farewell","escalation","cancel","clarification","unknown"}
INTENTS={"conceptual","procedural","troubleshooting","requirements","architecture","warranty","unknown"}
RELATIONS={"same_topic","new_topic","return_to_previous","independent_question","unknown"}
FACTS={"symptom","affected_scope","timeline","change_context","environment","error_message","version","location","frequency","observed_behavior","expected_behavior","attempted_action","attempt_result","technical_context"}
SCHEMA={"type":"object","additionalProperties":False,"properties":{"conversation_act":{"type":"string","enum":sorted(ACTS)},"intent":{"type":"string","enum":sorted(INTENTS)},"topic_relation":{"type":"string","enum":sorted(RELATIONS)},"entities":{"type":"array","items":{"type":"object"}},"facts":{"type":"array","items":{"type":"object"}},"requires_documents":{"type":"boolean"},"escalation_action":{"type":"string","enum":["none","start","continue","finish","cancel"]},"confidence":{"type":"number"},"reasoning_summary":{"type":"string"}},"required":["conversation_act","intent","topic_relation","entities","facts","requires_documents","escalation_action","confidence","reasoning_summary"]}

def _extract(text):
 text=str(text or "").strip();a=text.find("{");b=text.rfind("}")
 if a<0 or b<a:raise ValueError("incomplete_json")
 return json.loads(text[a:b+1])
def _proposal(act="clarification",intent="unknown",relation="same_topic",entities=None,facts=None,docs=False,esc="none",confidence=.35,summary="fallback"):
 action="respond_directly";question=None
 if act=="technical_request":action="retrieve" if docs else "respond_directly"
 elif act=="case_update":action="record_case_detail"
 elif act=="attempt":action="record_attempt";intent="troubleshooting"
 elif act=="attempt_result":action="record_attempt_result";intent="troubleshooting"
 elif act=="escalation":action={"start":"start_escalation","continue":"continue_escalation","finish":"continue_escalation","cancel":"cancel_all"}.get(esc,"continue_escalation");intent="escalation"
 elif act=="cancel":action="cancel_all";intent="cancel"
 elif act in {"clarification","unknown"}:action="ask_clarification";question="No estoy seguro de haber entendido. ¿Puedes precisar qué necesitas respecto al caso actual?"
 elif act=="capability":intent="capabilities"
 elif act in {"social","farewell"}:intent="social"
 return InterpreterProposal(act,intent,action,relation,entities or [],facts or [],question,confidence,summary)
def _normalize(raw,state):
 r=dict(raw or {});act=str(r.get("conversation_act") or "unknown");intent=str(r.get("intent") or "unknown");relation=str(r.get("topic_relation") or "unknown");docs=bool(r.get("requires_documents",False));esc=str(r.get("escalation_action") or "none")
 if act not in ACTS:act="unknown"
 if intent not in INTENTS:intent="unknown"
 if relation not in RELATIONS:relation="unknown"
 entities=[]
 for x in r.get("entities") or []:
  if not isinstance(x,dict):continue
  kind=str(x.get("kind") or "");name=str(x.get("canonical_name") or x.get("name") or x.get("matched_text") or "").strip()
  if kind in {"product","component","process"} and name:entities.append({"kind":kind,"canonical_id":str(x.get("canonical_id") or ""),"canonical_name":name,"matched_text":str(x.get("matched_text") or x.get("mention") or name),"confidence":float(x.get("confidence",r.get("confidence",0)) or 0)})
 facts=[];aliases={"scope":"affected_scope","action":"attempted_action","attempt":"attempted_action","result":"attempt_result","status":"change_context"}
 for x in r.get("facts") or []:
  if not isinstance(x,dict):continue
  category=aliases.get(str(x.get("type") or x.get("category") or "technical_context"),str(x.get("type") or x.get("category") or "technical_context"));value=str(x.get("value") or x.get("fact") or "").strip()
  if category in FACTS and value:facts.append({"type":category,"value":value,"confidence":float(x.get("confidence",r.get("confidence",0)) or 0),"correction":bool(x.get("correction",False)),"source":"semantic_current_turn"})
 categories={x["type"] for x in facts};attempts=getattr(getattr(state,"technical_case",None),"attempts",[]) or []
 invalid=(act=="technical_request" and intent=="unknown") or (act in {"capability","social","farewell"} and (entities or docs or intent not in {"unknown"})) or (act=="attempt" and "attempted_action" not in categories) or (act=="attempt_result" and ("attempt_result" not in categories or not attempts))
 if invalid:return _proposal(summary="fallback:incoherent_contract")
 return _proposal(act,intent,relation,entities,facts,docs,esc,float(r.get("confidence",0) or 0),str(r.get("reasoning_summary") or "")[:120])

class QwenInterpreter:
 def __init__(self,gateway,max_tokens=260):self.gateway=gateway;self.max_tokens=max(220,min(360,int(max_tokens)));self.last_trace={}
 def _request(self,message,state,response_schema,max_tokens,purpose):
  from app.llm_gateway.models import LLMRequest
  system="""Classify only the current conversational turn. Use canonical state only to resolve omitted context. A clear request about a failure, degraded behavior, impact or next technical validation is troubleshooting and requires documents. Definitions are conceptual, how-to instructions are procedural, prerequisites are requirements. Extract explicit symptoms, affected scope, attempts and results. Return one compact JSON object only, with every required field and no markdown."""
  payload={"current_message":message,"canonical_state":state.to_dict()}
  return self.gateway.complete(LLMRequest([{"role":"system","content":system},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],purpose,max_tokens,0.,response_schema))
 def interpret(self,message,state):
  first=self._request(message,state,SCHEMA,self.max_tokens,"agent_core_v2_current_turn")
  attempts=[{"stage":"structured","ok":bool(first.ok),"finish_reason":first.finish_reason,"error_code":first.error_code,"model":first.model}]
  candidate=first
  if not first.ok or not str(first.text or "").strip():
   second=self._request(message,state,None,min(260,self.max_tokens),"agent_core_v2_current_turn_recovery")
   attempts.append({"stage":"text_json_recovery","ok":bool(second.ok),"finish_reason":second.finish_reason,"error_code":second.error_code,"model":second.model})
   candidate=second
  try:
   raw=_extract(candidate.text) if candidate.ok else None
   proposal=_normalize(raw,state) if raw is not None else _proposal(summary="fallback:provider_after_recovery")
   parsed=raw is not None
  except Exception as exc:
   proposal=_proposal(summary="fallback:invalid_json_after_recovery");parsed=False;attempts[-1]["parse_error"]=type(exc).__name__
  self.last_trace={"original_message":message,"provider_ok":bool(candidate.ok),"finish_reason":candidate.finish_reason,"parsed":parsed,"recovery_used":len(attempts)>1,"attempts":attempts}
  return proposal
