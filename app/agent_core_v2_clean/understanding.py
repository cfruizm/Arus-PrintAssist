import json
from .contracts import UNDERSTANDING_SCHEMA
from .models import TurnUnderstanding
from .memory import compact_context,normalize_goal_updates
SYSTEM="""Semantic understanding for an enterprise printing-support assistant. The domain includes printing software, print-management and fleet-management platforms, printers, MFDs, scanning, accounting, consumables, installation, connectivity and operational processes. Interpret the current message with memory and the last assistant question. A short answer completes the pending question and never replaces the goal. Use answer_to_question only when last_assistant_question is present. A self-contained request that introduces a different operation or subject is a new_topic even when both requests belong to printing. Distinguish conceptual, procedural and troubleshooting. A new printing product remains in_scope. A genuinely unrelated self-contained request is independent and out_of_scope. Use the same language as the current user for current_goal, reasoning_summary and goal_updates values. goal_updates contains atomic facts only, never intent, status, summary, known_details, missing_detail, goal_complete or current_goal. Return one complete non-empty JSON object matching the schema. Keep reasoning_summary under 20 words."""
REQUIRED={"user_act","intent","topic_relation","domain_relevance","current_goal","goal_complete","goal_updates","case_updates","needs_clarification","clarification_target","should_retrieve","confidence","reasoning_summary"}
class ConversationUnderstanding:
 def __init__(self,gateway,max_tokens=300):self.gateway=gateway;self.max_tokens=max(220,min(420,int(max_tokens)));self.last_provider_result={};self.contract_valid=False;self.validation_error=None;self.normalization={"removed_goal_update_keys":[]}
 def _degraded(self,memory,reason):return TurnUnderstanding("follow_up",memory.pending_goal.intent or "unknown","same_topic","uncertain",memory.pending_goal.summary or memory.active_topic or "",False,{},[],False,None,False,0.0,reason,True)
 def _parse(self,text):
  text=str(text or "").strip();a=text.find("{");b=text.rfind("}")
  if a<0 or b<a:raise ValueError("json_object_missing")
  raw=json.loads(text[a:b+1])
  if not isinstance(raw,dict) or not raw:raise ValueError("empty_object")
  missing=REQUIRED-set(raw)
  if missing:raise ValueError("missing_fields:"+",".join(sorted(missing)))
  raw["goal_updates"],removed=normalize_goal_updates(raw.get("goal_updates"));self.normalization={"removed_goal_update_keys":removed}
  return TurnUnderstanding(**raw)
 def interpret(self,message,memory):
  from app.llm_gateway.models import LLMRequest
  r=self.gateway.complete(LLMRequest([{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps({"message":message,"context":compact_context(memory)},ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_clean_understanding",self.max_tokens,0.,UNDERSTANDING_SCHEMA));self.last_provider_result=r.to_dict();self.contract_valid=False;self.validation_error=None;self.normalization={"removed_goal_update_keys":[]}
  if not r.ok:self.validation_error="provider_error:"+str(r.error_code or "unknown");return self._degraded(memory,self.validation_error)
  try:x=self._parse(r.text);self.contract_valid=True;return x
  except Exception as exc:
   self.validation_error=str(exc);self.last_provider_result.setdefault("metadata",{})["contract_valid"]=False;self.last_provider_result["metadata"]["contract_error"]=self.validation_error;return self._degraded(memory,"invalid_understanding:"+self.validation_error)
