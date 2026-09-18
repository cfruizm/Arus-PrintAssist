import json
from .contracts import UNDERSTANDING_SCHEMA
from .models import TurnUnderstanding
from .memory import compact_context,normalize_goal_updates
SYSTEM="""Semantic understanding for an enterprise printing-support assistant. Interpret the current message using memory and the last assistant question. The current_goal must express the current request, not copy an earlier operation. Distinguish conceptual, procedural, requirements and troubleshooting. Use requirements for prerequisites, compatibility, constraints or conditions; use procedural for execution steps. A changed operation about the same subject refines the goal and remains same_topic. request_elaboration is valid only when the message depends on an active goal or last assistant question. answer_to_question supplies requested information; in troubleshooting encode its meaning as observation, affected_scope, attempted_action or attempt_result, never as a generic answer_to_question fact. Put symptoms and diagnostic facts in case_updates. Clarify only when one missing fact is indispensable. A clear conceptual request never needs clarification. Reuse memory facts. goal_updates contains atomic facts only, never structural fields. Return one complete JSON object matching the schema. Keep reasoning_summary under 20 words."""
REQUIRED={"user_act","intent","topic_relation","domain_relevance","current_goal","goal_complete","goal_updates","case_updates","needs_clarification","clarification_target","should_retrieve","confidence","reasoning_summary"}
class ConversationUnderstanding:
 def __init__(self,gateway,max_tokens=300):self.gateway=gateway;self.max_tokens=max(220,min(420,int(max_tokens)));self.last_provider_result={};self.contract_valid=False;self.validation_error=None;self.normalization={"removed_goal_update_keys":[]}
 def _degraded(self,memory,reason):return TurnUnderstanding("follow_up",memory.pending_goal.intent or "unknown","same_topic","uncertain",memory.pending_goal.summary or memory.active_topic or "",False,{},[],False,None,False,0.,reason,True)
 def _parse(self,text):
  text=str(text or "").strip();a=text.find("{");b=text.rfind("}")
  if a<0 or b<a:raise ValueError("json_object_missing")
  raw=json.loads(text[a:b+1]);missing=REQUIRED-set(raw)
  if not isinstance(raw,dict) or not raw:raise ValueError("empty_object")
  if missing:raise ValueError("missing_fields:"+",".join(sorted(missing)))
  raw["goal_updates"],removed=normalize_goal_updates(raw.get("goal_updates"));self.normalization={"removed_goal_update_keys":removed};return TurnUnderstanding(**raw)
 def interpret(self,message,memory):
  from app.llm_gateway.models import LLMRequest
  r=self.gateway.complete(LLMRequest([{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps({"message":message,"context":compact_context(memory)},ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_clean_understanding",self.max_tokens,0.,UNDERSTANDING_SCHEMA));self.last_provider_result=r.to_dict();self.contract_valid=False;self.validation_error=None;self.normalization={"removed_goal_update_keys":[]}
  if not r.ok:self.validation_error="provider_error:"+str(r.error_code or "unknown");return self._degraded(memory,self.validation_error)
  try:
   x=self._parse(r.text);corrections=[]
   if x.user_act=="answer_to_question" and not memory.last_assistant_question:x.user_act="follow_up" if memory.active_topic else "new_request";corrections.append("answer_without_pending_question_normalized")
   if x.user_act=="request_elaboration":
    if not memory.active_topic and not memory.last_assistant_question:x.user_act="new_request";x.topic_relation="new_topic";corrections.append("orphan_elaboration_to_new_request")
    else:x.topic_relation="same_topic";x.should_retrieve=True;corrections.append("referential_operational_retrieval_enforced")
   if x.intent=="conceptual" and x.domain_relevance=="in_scope":x.needs_clarification=False;x.clarification_target=None;x.should_retrieve=True
   if x.needs_clarification and not str(x.clarification_target or "").strip():x.needs_clarification=False;corrections.append("empty_clarification_suppressed")
   if x.topic_relation=="same_topic" and memory.pending_goal.summary and x.current_goal and x.current_goal.casefold()!=memory.pending_goal.summary.casefold():corrections.append("same_topic_goal_refined")
   if x.intent=="troubleshooting":
    present={str(a.get("type") or "") for a in x.case_updates}
    for key in ("symptom","observation","affected_scope","attempted_action","attempt_result"):
     value=str((x.goal_updates or {}).get(key) or "").strip()
     if value and key not in present:x.case_updates.append({"type":key,"value":value});corrections.append("goal_fact_promoted_to_case:"+key)
   self.normalization["structural_corrections"]=corrections;self.contract_valid=True;return x
  except Exception as exc:self.validation_error=str(exc);return self._degraded(memory,"invalid_understanding:"+self.validation_error)
