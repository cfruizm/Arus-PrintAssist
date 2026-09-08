from __future__ import annotations
import json
from .models import InterpreterProposal
ACTS={"technical_request","case_update","attempt","attempt_result","capability","social","farewell","escalation","cancel","clarification","unknown"}
INTENTS={"conceptual","procedural","troubleshooting","requirements","architecture","warranty","unknown"}
RELATIONS={"same_topic","new_topic","return_to_previous","independent_question","unknown"}
FACTS={"symptom","affected_scope","timeline","change_context","environment","error_message","version","location","frequency","observed_behavior","expected_behavior","attempted_action","attempt_result","technical_context"}
SCHEMA={"type":"object","properties":{"conversation_act":{"type":"string","enum":sorted(ACTS)},"intent":{"type":"string","enum":sorted(INTENTS)},"topic_relation":{"type":"string","enum":sorted(RELATIONS)},"entities":{"type":"array","items":{"type":"object"}},"facts":{"type":"array","items":{"type":"object"}},"requires_documents":{"type":"boolean"},"escalation_action":{"type":"string","enum":["none","start","continue","finish","cancel"]},"confidence":{"type":"number"},"reasoning_summary":{"type":"string"}},"required":["conversation_act","intent","topic_relation","entities","facts","requires_documents","escalation_action","confidence","reasoning_summary"]}
def _extract(text):
 text=str(text or "").strip();a=text.find("{");b=text.rfind("}")
 if a<0 or b<a:raise ValueError("incomplete_json")
 return json.loads(text[a:b+1])
def _proposal(act="clarification",intent="unknown",relation="same_topic",entities=None,facts=None,docs=False,summary=""):
 return InterpreterProposal(act,intent,"ask_clarification",relation,entities or [],facts or [],"¿Podrías ampliar la solicitud?",.35,summary)
def _normalize(r,state):
 act=str(r.get("conversation_act") or "unknown");intent=str(r.get("intent") or "unknown");rel=str(r.get("topic_relation") or "unknown")
 if act not in ACTS:act="unknown"
 if intent not in INTENTS:intent="unknown"
 if rel not in RELATIONS:rel="unknown"
 docs=bool(r.get("requires_documents")); entities=r.get("entities") if isinstance(r.get("entities"),list) else []; facts=r.get("facts") if isinstance(r.get("facts"),list) else []
 if act in {"social","farewell","capability"}: docs=False;entities=[];rel="independent_question"
 # A technical intent with a concrete subject or an active topic is an answerable request.
 # The model may label it clarification while explaining that it is a direct request.
 active=bool(getattr(getattr(state,"active_topic",None),"products",[]) or getattr(getattr(state,"active_topic",None),"processes",[]))
 summary=str(r.get("reasoning_summary") or "").casefold()
 direct_semantics=any(x in summary for x in ("direct request","direct query","requests technical","requests general","procedural request","prerequisites"))
 if act=="clarification" and intent in INTENTS-{"unknown"} and (entities or active or direct_semantics):act="technical_request"
 if act=="technical_request" and intent in INTENTS-{"unknown"}: docs=True
 if act=="technical_request" and intent in INTENTS-{"unknown"}: action="retrieve" if docs else "respond_directly";question=None
 elif act=="clarification":action="ask_clarification";question="¿Podrías ampliar la solicitud?"
 else:action="respond_directly";question=None
 return InterpreterProposal(act,intent,action,rel,entities,facts,question,float(r.get("confidence",0) or 0),str(r.get("reasoning_summary") or "")[:180])
class QwenInterpreter:
 def __init__(self,gateway,max_tokens=320):self.gateway=gateway;self.max_tokens=max(260,min(420,int(max_tokens)));self.last_trace={};self.previous_user_message=None
 def interpret(self,message,state):
  from app.llm_gateway.models import LLMRequest
  system="""Interpret the current turn semantically. The immediately previous user message is supplied only to resolve elliptical follow-ups such as 'what is the procedure?'. Never let the previous intent override a clear current request. conceptual=purpose/definition; procedural=how to perform an action or analyze/use something; requirements=prerequisites, compatibility or capacity; troubleshooting=failure/diagnosis. A clear technical request is technical_request, not clarification merely because version/model details are absent. Determine topic relation by meaning: aliases, parent solutions and components in the same ongoing task remain same_topic; a different product, business process or dashboard is new_topic. A newly mentioned process must not inherit an unrelated active product. Return compact JSON only."""
  payload={"current_message":message,"previous_user_message":self.previous_user_message,"canonical_state":state.to_dict()}
  res=self.gateway.complete(LLMRequest([{"role":"system","content":system},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_current_turn",self.max_tokens,0.,SCHEMA))
  self.last_trace={"original_message":message,"previous_user_message":self.previous_user_message,"provider_ok":bool(res.ok),"finish_reason":res.finish_reason}
  self.previous_user_message=message
  if not res.ok or res.finish_reason=="length":return _proposal(summary="fallback:provider")
  try:return _normalize(_extract(res.text),state)
  except Exception:return _proposal(summary="fallback:invalid_json")
class ScriptedInterpreter:
 def __init__(self,outputs):self.outputs=list(outputs);self.i=0;self.last_trace={}
 def interpret(self,message,state):raw=self.outputs[self.i];self.i+=1;return _normalize(raw,state)
