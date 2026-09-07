from __future__ import annotations
import json
from .models import InterpreterProposal
ACTS={"technical_request","clarification","capability","social","farewell","escalation","cancel","attempt","attempt_result"}
INTENTS={"conceptual","procedural","troubleshooting","requirements","architecture","warranty","escalation","cancel","unknown"}
RELATIONS={"same_topic","new_topic","return_to_previous","independent_question","unknown"}
TECHNICAL_INTENTS={"conceptual","procedural","troubleshooting","requirements","architecture","warranty"}
FACTS={"symptom","affected_scope","attempted_action","attempt_result","timeline","change_context","environment","error_message","technical_context"}
SCHEMA={"type":"object","properties":{"conversation_act":{"type":"string"},"intent":{"type":"string"},"topic_relation":{"type":"string"},"entities":{"type":"array"},"facts":{"type":"array"},"requires_documents":{"type":"boolean"},"escalation_action":{"type":"string"},"confidence":{"type":"number"},"reasoning_summary":{"type":"string"}},"required":["conversation_act","intent","topic_relation","entities","facts","requires_documents","escalation_action","confidence","reasoning_summary"]}
def _proposal(act="clarification",intent="unknown",relation="same_topic",entities=None,facts=None,docs=False,esc="none",confidence=.35,summary="fallback"):
 action="retrieve" if docs else "ask_clarification"
 if act=="escalation":action={"start":"start_escalation","continue":"continue_escalation","finish":"continue_escalation","cancel":"cancel_all"}.get(esc,"continue_escalation");intent="escalation"
 elif act=="cancel":action="cancel_all";intent="cancel"
 elif act=="attempt":action="record_attempt"
 elif act=="attempt_result":action="record_attempt_result"
 return InterpreterProposal(act,intent,action,relation,entities or [],facts or [],None if action!="ask_clarification" else "No estoy seguro de haber entendido. ¿Puedes precisar qué necesitas respecto al caso actual?",confidence,summary)
def _extract(text):
 text=str(text or "").strip();start=text.find("{");end=text.rfind("}")
 if start<0 or end<start:raise ValueError("incomplete_json")
 return json.loads(text[start:end+1])
def _recover_partial(text):
 text=str(text or "");out={}
 for field in ("conversation_act","intent","topic_relation","escalation_action","reasoning_summary"):
  marker='"'+field+'"';pos=text.find(marker)
  if pos<0:continue
  colon=text.find(":",pos+len(marker));quote=text.find('"',colon+1);end=text.find('"',quote+1)
  if colon>=0 and quote>=0 and end>quote:out[field]=text[quote+1:end]
 for field in ("requires_documents",):
  marker='"'+field+'"';pos=text.find(marker)
  if pos>=0:
   tail=text[text.find(":",pos)+1:].lstrip();out[field]=tail.startswith("true")
 marker='"confidence"';pos=text.find(marker)
 if pos>=0:
  tail=text[text.find(":",pos)+1:].lstrip();num=""
  for ch in tail:
   if ch in "0123456789.-":num+=ch
   else:break
  try:out["confidence"]=float(num)
  except:pass
 if out.get("intent") in TECHNICAL_INTENTS and float(out.get("confidence",0) or 0)>=.6:
  out.setdefault("conversation_act","technical_request");out.setdefault("topic_relation","same_topic");out["requires_documents"]=True;out.setdefault("entities",[]);out.setdefault("facts",[]);out.setdefault("escalation_action","none");out.setdefault("reasoning_summary","recovered_from_complete_structural_fields");return out
 return None
def _normalize(r,state):
 act=str(r.get("conversation_act") or "clarification");intent=str(r.get("intent") or "unknown");relation=str(r.get("topic_relation") or "same_topic");docs=bool(r.get("requires_documents",False));esc=str(r.get("escalation_action") or "none");confidence=float(r.get("confidence",0) or 0)
 if act not in ACTS:act="clarification"
 if intent not in INTENTS:intent="unknown"
 if relation not in RELATIONS:relation="unknown"
 entities=[]
 for x in r.get("entities") or []:
  if not isinstance(x,dict):continue
  kind=str(x.get("kind") or x.get("type") or x.get("entity_type") or "").replace("entity_","");name=str(x.get("canonical_name") or x.get("name") or x.get("surface_form") or "").strip()
  if kind in {"product","component","process"} and name:entities.append({"kind":kind,"canonical_id":str(x.get("canonical_id") or ""),"canonical_name":name,"matched_text":str(x.get("matched_text") or x.get("mention") or x.get("surface_form") or name),"confidence":float(x.get("confidence",confidence) or 0)})
 facts=[];aliases={"scope":"affected_scope","action":"attempted_action","attempt":"attempted_action","result":"attempt_result","status":"change_context"}
 for x in r.get("facts") or []:
  if not isinstance(x,dict):continue
  raw=str(x.get("type") or x.get("category") or x.get("key") or x.get("field") or "technical_context");category=aliases.get(raw,raw);value=str(x.get("value") or x.get("fact") or "").strip()
  if category in FACTS and value:facts.append({"type":category,"value":value,"confidence":float(x.get("confidence",confidence) or 0),"correction":bool(x.get("correction",False)),"source":"semantic_current_turn"})
 if intent in TECHNICAL_INTENTS and confidence>=.6 and act in {"clarification","unknown"}:act="technical_request";docs=True
 categories={x["type"] for x in facts};attempts=getattr(getattr(state,"technical_case",None),"attempts",[]) or []
 invalid=(act=="technical_request" and intent=="unknown") or (act in {"capability","social","farewell"} and (entities or docs or intent not in {"unknown"})) or (act=="attempt" and "attempted_action" not in categories) or (act=="attempt_result" and ("attempt_result" not in categories or not attempts))
 if invalid:return _proposal(relation="same_topic",summary="fallback:incoherent_contract")
 return _proposal(act,intent,relation,entities,facts,docs,esc,confidence,str(r.get("reasoning_summary") or "")[:160])
class QwenInterpreter:
 def __init__(self,gateway,max_tokens=300):self.gateway=gateway;self.max_tokens=max(260,min(380,int(max_tokens)));self.last_trace={}
 def interpret(self,message,state):
  from app.llm_gateway.models import LLMRequest
  system="""Interpret only the current turn using canonical state to resolve omitted references. Every clear conceptual, procedural, troubleshooting, requirements, architecture or warranty need is technical_request and requires_documents=true. A short answer can complete the immediately preceding clarification and must not discard that request. Use clarification only when no technical need can be determined. Extract compact JSON only, with a reasoning_summary under 35 words and no inferred entities presented as canonical."""
  payload={"current_message":message,"canonical_state":state.to_dict()};res=self.gateway.complete(LLMRequest([{"role":"system","content":system},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_current_turn",self.max_tokens,0.,SCHEMA));self.last_trace={"original_message":message,"provider_ok":bool(res.ok),"finish_reason":res.finish_reason,"recovery_used":False}
  if not res.ok:return _proposal(summary="fallback:provider")
  try:raw=_extract(res.text)
  except Exception:
   raw=_recover_partial(res.text)
   if raw is None:return _proposal(summary="fallback:invalid_json")
   self.last_trace["recovery_used"]=True
  try:return _normalize(raw,state)
  except Exception:return _proposal(summary="fallback:normalization")
class ScriptedInterpreter:
 def __init__(self,items):self.items=list(items);self.last_trace={}
 def interpret(self,message,state):return _normalize(self.items.pop(0),state)
