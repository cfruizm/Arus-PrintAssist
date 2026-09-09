from __future__ import annotations
import json
from .models import InterpreterProposal

ACTS={"technical_request","case_update","attempt","attempt_result","capability","social","farewell","escalation","cancel","clarification","unknown"}
INTENTS={"conceptual","procedural","troubleshooting","requirements","architecture","warranty","unknown"}
RELATIONS={"same_topic","new_topic","return_to_previous","independent_question","unknown"}
FACTS={"symptom","affected_scope","timeline","change_context","environment","error_message","version","location","frequency","observed_behavior","expected_behavior","attempted_action","attempt_result","technical_context"}
SCHEMA={"type":"object","properties":{"conversation_act":{"type":"string","enum":sorted(ACTS)},"intent":{"type":"string","enum":sorted(INTENTS)},"topic_relation":{"type":"string","enum":sorted(RELATIONS)},"entities":{"type":"array","items":{"type":"object"}},"facts":{"type":"array","items":{"type":"object"}},"requires_documents":{"type":"boolean"},"escalation_action":{"type":"string","enum":["none","start","continue","finish","cancel"]},"confidence":{"type":"number"},"reasoning_summary":{"type":"string"},"domain_relevance":{"type":"string","enum":["in_scope","out_of_scope","uncertain"]},"domain_confidence":{"type":"number"}},"required":["conversation_act","intent","topic_relation","entities","facts","requires_documents","escalation_action","confidence","reasoning_summary","domain_relevance","domain_confidence"]}

def _extract(text):
 text=str(text or "").strip();a=text.find("{");b=text.rfind("}")
 if a<0 or b<a:raise ValueError("incomplete_json")
 return json.loads(text[a:b+1])
def _active_intent(state):return getattr(getattr(state,"active_topic",None),"intent",None)
def _proposal(act="clarification",intent="unknown",relation="same_topic",entities=None,facts=None,docs=False,esc="none",confidence=.35,summary="fallback",domain_relevance="uncertain",domain_confidence=0.):
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
 return InterpreterProposal(conversation_act=act,intent=intent,requested_action=action,topic_relation=relation,entities=entities or [],facts=facts or [],clarification_question=question,confidence=confidence,reasoning_summary=summary,domain_relevance=domain_relevance,domain_confidence=domain_confidence)
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
 # Contract coherence. These checks are semantic structure, not message keywords.
 invalid=(act=="technical_request" and intent=="unknown") or (act in {"capability","social","farewell"} and (entities or docs or intent not in {"unknown"})) or (act=="attempt" and "attempted_action" not in categories) or (act=="attempt_result" and ("attempt_result" not in categories or not attempts))
 if invalid:return _proposal(relation="same_topic",summary="fallback:incoherent_contract")
 return _proposal(act,intent,relation,entities,facts,docs,esc,float(r.get("confidence",0) or 0),str(r.get("reasoning_summary") or "")[:120],str(r.get("domain_relevance") or "uncertain"),float(r.get("domain_confidence",0) or 0))
class QwenInterpreter:
 def __init__(self,gateway,max_tokens=260):self.gateway=gateway;self.max_tokens=max(220,min(320,int(max_tokens)));self.last_trace={}
 def interpret(self,message,state):
  from app.llm_gateway.models import LLMRequest
  system="""The assistant has a bounded mission: enterprise printing support, including print devices, print management software, print infrastructure, supplies, warranties and service operations. Determine domain_relevance semantically from the current request and canonical context. Greetings, farewells, capability questions and short references to an active printing case are in_scope. A clearly unrelated knowledge request is out_of_scope. An ambiguous message that may refer to the active printing case is uncertain. This classification controls only scope; do not redesign or replace the existing escalation action or workflow.
Interpret only the current conversational turn, using canonical state for references and omitted entities. Product and case context may persist, but the previous intent must never override a clear current request. technical_request intent: conceptual only for definition or purpose; procedural for any request asking how to perform, configure or assign an operation; requirements for prerequisites or dependencies; troubleshooting whenever an attempted or desired operation is failing, blocked, unavailable, missing or cannot be completed; architecture or warranty when applicable. For troubleshooting, extract the inability or observed behavior as a symptom fact. A self-contained request unrelated to printing is independent and out_of_scope, never a clarification of the active case. Check the final intent against the current request before returning JSON. capability concerns the assistant itself and must have no product entity or documents. social and farewell are lateral conversation acts, must have no product entity, no documents, and must not change the technical topic. Extract error messages and inability to perform an operation as error_message, symptom or observed_behavior, not generic context. Escalation uses the existing canonical escalation action. Return compact JSON only."""
  payload={"current_message":message,"canonical_state":state.to_dict()};res=self.gateway.complete(LLMRequest([{"role":"system","content":system},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_current_turn",self.max_tokens,0.,SCHEMA))
  self.last_trace={"original_message":message,"provider_ok":bool(res.ok),"finish_reason":res.finish_reason}
  if not res.ok or res.finish_reason=="length":return _proposal(summary="fallback:provider")
  try:return _normalize(_extract(res.text),state)
  except Exception:return _proposal(summary="fallback:invalid_json")
class ScriptedInterpreter:
 def __init__(self,outputs):self.outputs=list(outputs);self.i=0;self.last_trace={}
 def interpret(self,message,state):raw=self.outputs[self.i];self.i+=1;return _normalize(raw,state)


