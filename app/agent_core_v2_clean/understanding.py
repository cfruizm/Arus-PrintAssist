import json
from .contracts import UNDERSTANDING_SCHEMA
from .models import TurnUnderstanding
from .memory import compact_context,normalize_goal_updates
SYSTEM="""Semantic understanding for an enterprise printing-support assistant. Interpret the current message using memory and the last assistant question. Distinguish conceptual, procedural and troubleshooting. The current_goal must express what the user is asking now, not copy an earlier goal when the requested operation changed. A changed operation about the same subject refines the active goal and remains same_topic; new_topic is for a genuinely different subject. A referential continuation that depends on the active goal is follow_up and same_topic even when no assistant question is pending. request_elaboration means the user asks how to perform, verify, locate or understand the immediately previous question or recommended action without answering it. answer_to_question is reserved only for a message that actually supplies the requested information. Help first. Clarify only when one missing fact is indispensable because plausible interpretations produce materially different or unsafe answers, or retrieval would otherwise bind the request to an arbitrary platform, component or architecture. Ask only the single scope fact needed to ground the answer. Do not require version, model, environment or implementation details by routine. A clear self-contained conceptual request is answerable as written and never needs clarification. Reuse facts from memory. Preserve the pending goal when the user answers a prior question. An ambiguous request that still plausibly belongs to printing support is uncertain or in_scope, not out_of_scope. goal_updates contains atomic facts only, never structural fields. Use the user's language for values. Return one complete JSON object matching the schema. Keep reasoning_summary under 20 words."""
REQUIRED={"user_act","intent","topic_relation","domain_relevance","current_goal","goal_complete","goal_updates","case_updates","needs_clarification","clarification_target","should_retrieve","confidence","reasoning_summary"}
class ConversationUnderstanding:
 def __init__(self,gateway,max_tokens=300):self.gateway=gateway;self.max_tokens=max(220,min(420,int(max_tokens)));self.last_provider_result={};self.contract_valid=False;self.validation_error=None;self.normalization={"removed_goal_update_keys":[]}
 def _degraded(self,memory,reason):return TurnUnderstanding("follow_up",memory.pending_goal.intent or "unknown","same_topic","uncertain",memory.pending_goal.summary or memory.active_topic or "",False,{},[],False,None,False,0.,reason,True)
 def _parse(self,text):
  text=str(text or "").strip();a=text.find("{");b=text.rfind("}")
  if a<0 or b<a:raise ValueError("json_object_missing")
  raw=json.loads(text[a:b+1])
  if not isinstance(raw,dict) or not raw:raise ValueError("empty_object")
  missing=REQUIRED-set(raw)
  if missing:raise ValueError("missing_fields:"+",".join(sorted(missing)))
  raw["goal_updates"],removed=normalize_goal_updates(raw.get("goal_updates"));self.normalization={"removed_goal_update_keys":removed};return TurnUnderstanding(**raw)
 def interpret(self,message,memory):
  from app.llm_gateway.models import LLMRequest
  r=self.gateway.complete(LLMRequest([{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps({"message":message,"context":compact_context(memory)},ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_clean_understanding",self.max_tokens,0.,UNDERSTANDING_SCHEMA));self.last_provider_result=r.to_dict();self.contract_valid=False;self.validation_error=None;self.normalization={"removed_goal_update_keys":[]}
  if not r.ok:self.validation_error="provider_error:"+str(r.error_code or "unknown");return self._degraded(memory,self.validation_error)
  try:
   x=self._parse(r.text);corrections=[]
   if x.user_act=="answer_to_question" and not memory.last_assistant_question:
    if x.topic_relation=="same_topic" and memory.active_topic:x.user_act="follow_up";corrections.append("answer_without_pending_question_to_follow_up")
    else:x.user_act="new_request";corrections.append("answer_without_pending_question_to_new_request")
   if x.user_act=="request_elaboration":
    x.topic_relation="same_topic";x.needs_clarification=False;x.clarification_target=None
    if memory.last_assistant_question and (not x.current_goal or x.current_goal.casefold()==str(memory.pending_goal.summary or "").casefold()):
     x.current_goal=f"Explicar cómo realizar o verificar: {memory.last_assistant_question}"
     corrections.append("referential_elaboration_anchored_to_last_question")
   if x.topic_relation=="same_topic" and memory.pending_goal.summary and x.current_goal and x.current_goal.casefold()!=memory.pending_goal.summary.casefold():
    corrections.append("same_topic_goal_refined")
   if x.domain_relevance=="out_of_scope" and x.needs_clarification and str(x.clarification_target or "").strip():x.domain_relevance="in_scope";x.should_retrieve=False;corrections.append("resolvable_scope_uncertainty_to_material_clarification")
   if x.intent=="conceptual" and x.domain_relevance=="in_scope" and x.user_act in {"new_request","independent_question","follow_up"} and str(x.current_goal or "").strip():
    if x.needs_clarification:corrections.append("non_material_conceptual_clarification_suppressed")
    x.needs_clarification=False;x.clarification_target=None
    if not x.should_retrieve:corrections.append("in_scope_conceptual_retrieval_enforced")
    x.should_retrieve=True
   if x.needs_clarification and not str(x.clarification_target or "").strip():x.needs_clarification=False;corrections.append("empty_clarification_suppressed")
   if x.topic_relation=="new_topic":
    anchor=(str(message)+" "+str(x.current_goal)).casefold();kept={};removed=[]
    for k,v in x.goal_updates.items():
     value=str(v).strip()
     if value and value.casefold() in anchor:kept[k]=value
     else:removed.append(str(k))
    x.goal_updates=kept
    if removed:self.normalization["removed_unanchored_new_topic_keys"]=sorted(removed)
   self.normalization["structural_corrections"]=corrections;self.contract_valid=True;return x
  except Exception as exc:
   self.validation_error=str(exc);self.last_provider_result.setdefault("metadata",{})["contract_valid"]=False;self.last_provider_result["metadata"]["contract_error"]=self.validation_error;return self._degraded(memory,"invalid_understanding:"+self.validation_error)
