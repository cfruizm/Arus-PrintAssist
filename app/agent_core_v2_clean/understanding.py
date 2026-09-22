import json
from .contracts import UNDERSTANDING_SCHEMA
from .models import TurnUnderstanding
from .memory import compact_context,normalize_goal_updates
SYSTEM="""Semantic understanding for an enterprise printing-support assistant. Interpret the current message using memory and the last assistant question. The current_goal must express the current request, not copy an earlier operation. Distinguish conceptual, procedural, requirements and troubleshooting. Use requirements for prerequisites, compatibility, constraints or conditions; use procedural for execution steps. A changed operation about the same subject refines the goal and remains same_topic. request_elaboration is valid only when the message depends on an active goal or last assistant question. answer_to_question supplies requested information. Put symptoms and diagnostic facts in case_updates. Clarify only when one missing fact is indispensable. A clear conceptual request never needs clarification. Return one complete JSON object matching the schema. No fields outside the schema. Keep reasoning_summary under 20 words."""
REQUIRED={"user_act","intent","topic_relation","domain_relevance","current_goal","goal_complete","goal_updates","case_updates","needs_clarification","clarification_target","should_retrieve","confidence","reasoning_summary"}
ALLOWED=set(REQUIRED)
ALIASES={"clarification_needed":"needs_clarification","clarification_question":"clarification_target"}
class ConversationUnderstanding:
 def __init__(self,gateway,max_tokens=300):self.gateway=gateway;self.max_tokens=max(220,min(420,int(max_tokens)));self.last_provider_result={};self.contract_valid=False;self.validation_error=None;self.normalization={"removed_goal_update_keys":[]}
 def _degraded(self,memory,reason):return TurnUnderstanding("follow_up",memory.pending_goal.intent or "unknown","same_topic","uncertain",memory.pending_goal.summary or memory.active_topic or "",False,{},[],False,None,False,0.,reason,True)
 def _degraded_current(self,message,reason):
  text=" ".join(str(message or "").split());low=text.casefold()
  intent="conceptual" if any(x in low for x in ("document","informacion","información","que muestra","qué muestra","analizar")) else "procedural" if any(x in low for x in ("como ","cómo ","procedimiento","instalar","configurar","asignar","actualizar")) else "unknown"
  return TurnUnderstanding("new_request",intent,"new_topic","in_scope" if intent!="unknown" else "uncertain",text,False,{"subject":text} if text else {},[],False,None,True,0.35,reason,True)
 def _parse(self,text):
  text=str(text or "").strip();a=text.find("{");b=text.rfind("}")
  if a<0 or b<a:raise ValueError("json_object_missing")
  raw=json.loads(text[a:b+1])
  if not isinstance(raw,dict) or not raw:raise ValueError("empty_object")
  aliases={}
  for src,dst in ALIASES.items():
   if dst not in raw and src in raw:raw[dst]=raw[src];aliases[src]=dst
  updates=raw.get("goal_updates")
  if isinstance(updates,list):
   facts=[str(x.get("fact") or x.get("value") or "").strip() for x in updates if isinstance(x,dict)]
   facts=[x for x in facts if x];raw["goal_updates"]={"subject":facts[0]} if facts else {}
   if facts and not raw.get("current_goal"):raw["current_goal"]=facts[0]
   aliases["goal_updates:list"]="goal_updates:dict"
  probe=" ".join((str(raw.get("current_goal") or ""),str(raw.get("goal_updates") or ""))).casefold()
  raw.setdefault("user_act","new_request");raw.setdefault("intent","conceptual" if any(x in probe for x in ("document","analiz","informacion","información")) else "procedural")
  raw.setdefault("topic_relation","new_topic");raw.setdefault("domain_relevance","in_scope");raw.setdefault("current_goal",probe.strip() or "Atender la solicitud actual")
  raw.setdefault("goal_complete",False);raw.setdefault("goal_updates",{});raw.setdefault("case_updates",[]);raw.setdefault("needs_clarification",False);raw.setdefault("clarification_target",None);raw.setdefault("should_retrieve",True);raw.setdefault("confidence",0.75);raw.setdefault("reasoning_summary","provider_payload_normalized")
  missing=REQUIRED-set(raw)
  if missing:raise ValueError("missing_fields:"+",".join(sorted(missing)))
  for legacy in ALIASES:raw.pop(legacy,None)
  unknown=sorted(set(raw)-ALLOWED);clean={key:raw[key] for key in ALLOWED};clean["goal_updates"],removed=normalize_goal_updates(clean.get("goal_updates"))
  self.normalization={"removed_goal_update_keys":removed,"schema_aliases":aliases,"removed_unknown_fields":unknown,"contract_repaired":bool(aliases or unknown)}
  return TurnUnderstanding(**clean)
 def _normalize(self,x,memory):
  corrections=[]
  if x.user_act=="answer_to_question" and not memory.last_assistant_question:x.user_act="follow_up" if memory.active_topic else "new_request";corrections.append("answer_without_pending_question_normalized")
  if x.user_act=="request_elaboration":
   if not memory.active_topic and not memory.last_assistant_question:x.user_act="new_request";x.topic_relation="new_topic";corrections.append("orphan_elaboration_to_new_request")
   elif x.topic_relation=="new_topic":x.user_act="new_request";x.should_retrieve=True;corrections.append("provider_new_topic_preserved")
   else:x.topic_relation="same_topic";x.should_retrieve=True;corrections.append("referential_operational_retrieval_enforced")
  if x.intent=="conceptual" and x.domain_relevance=="in_scope":x.needs_clarification=False;x.clarification_target=None;x.should_retrieve=True
  if x.needs_clarification and not str(x.clarification_target or "").strip():x.needs_clarification=False;corrections.append("empty_clarification_suppressed")
  if x.intent=="troubleshooting":
   present={str(a.get("type") or "") for a in x.case_updates}
   for key in ("symptom","observation","affected_scope","attempted_action","attempt_result"):
    value=str((x.goal_updates or {}).get(key) or "").strip()
    if value and key not in present:x.case_updates.append({"type":key,"value":value});corrections.append("goal_fact_promoted_to_case:"+key)
  self.normalization.setdefault("structural_corrections",[]);self.normalization["structural_corrections"].extend(corrections);return x
 def interpret(self,message,memory):
  from app.llm_gateway.models import LLMRequest
  req=lambda payload,purpose:self.gateway.complete(LLMRequest([{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],purpose,self.max_tokens,0.,UNDERSTANDING_SCHEMA))
  r=req({"message":message,"context":compact_context(memory)},"agent_core_v2_clean_understanding");self.last_provider_result=r.to_dict();self.contract_valid=False;self.validation_error=None;self.normalization={"removed_goal_update_keys":[]}
  if not r.ok:self.validation_error="provider_error:"+str(r.error_code or "unknown");return self._degraded_current(message,self.validation_error)
  try:x=self._parse(r.text);self.contract_valid=True;return self._normalize(x,memory)
  except Exception as exc:
   first_error=str(exc);retry=req({"message":message,"context":compact_context(memory),"invalid_output":str(r.text or "")[:4000],"validation_error":first_error,"instruction":"Return only a complete JSON object matching the schema without extra fields."},"agent_core_v2_clean_understanding_repair")
   self.last_provider_result={"initial":r.to_dict(),"repair":retry.to_dict(),"repair_attempted":True};self.normalization={"removed_goal_update_keys":[],"repair_attempted":True,"repair_succeeded":False}
   if retry.ok:
    try:x=self._parse(retry.text);self.contract_valid=True;self.validation_error=None;self.normalization["repair_attempted"]=True;self.normalization["repair_succeeded"]=True;return self._normalize(x,memory)
    except Exception as retry_exc:self.validation_error=str(retry_exc)
   else:self.validation_error="repair_provider_error:"+str(retry.error_code or "unknown")
   return self._degraded_current(message,"invalid_understanding:"+str(self.validation_error or first_error))
