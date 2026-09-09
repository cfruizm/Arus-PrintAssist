import json
from .contracts import UNDERSTANDING_SCHEMA
from .models import TurnUnderstanding
from .memory import compact_context
SYSTEM="""Semantic understanding for an enterprise printing-support assistant. The domain includes printing software, print-management and fleet-management platforms, printers, MFDs, scanning, accounting, consumables, installation, connectivity and operational processes. Interpret the current message with memory and the last assistant question. A short answer completes the pending question and never replaces the goal. Do not classify a request for help as a failure unless a malfunction is reported. Distinguish conceptual, procedural and troubleshooting. A new printing product remains in_scope. A genuinely unrelated self-contained request is independent and out_of_scope. Return one complete JSON object matching the schema. Never return an empty object. Keep reasoning_summary under 20 words and goal_updates to essential facts only."""
REQUIRED={"user_act","intent","topic_relation","domain_relevance","current_goal","goal_complete","goal_updates","case_updates","needs_clarification","clarification_target","should_retrieve","confidence","reasoning_summary"}
class ConversationUnderstanding:
 def __init__(self,gateway,max_tokens=300):self.gateway=gateway;self.max_tokens=max(220,min(420,int(max_tokens)));self.last_provider_result={};self.contract_valid=False;self.validation_error=None
 def _degraded(self,memory,reason):
  return TurnUnderstanding("follow_up",memory.pending_goal.intent or "unknown","same_topic","uncertain",memory.pending_goal.summary or memory.active_topic or "",False,{},[],False,None,False,0.0,reason,True)
 def _parse(self,text):
  text=str(text or "").strip();start=text.find("{");end=text.rfind("}")
  if start<0 or end<start:raise ValueError("json_object_missing")
  raw=json.loads(text[start:end+1])
  if not isinstance(raw,dict) or not raw:raise ValueError("empty_object")
  missing=REQUIRED-set(raw)
  if missing:raise ValueError("missing_fields:"+",".join(sorted(missing)))
  return TurnUnderstanding(**raw)
 def interpret(self,message,memory):
  from app.llm_gateway.models import LLMRequest
  payload={"message":message,"context":compact_context(memory)}
  r=self.gateway.complete(LLMRequest([{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_clean_understanding",self.max_tokens,0.,UNDERSTANDING_SCHEMA));self.last_provider_result=r.to_dict();self.contract_valid=False;self.validation_error=None
  if not r.ok:self.validation_error="provider_error:"+str(r.error_code or "unknown");return self._degraded(memory,self.validation_error)
  try:
   result=self._parse(r.text);self.contract_valid=True;return result
  except Exception as exc:
   self.validation_error=str(exc);self.last_provider_result.setdefault("metadata",{})["contract_valid"]=False;self.last_provider_result["metadata"]["contract_error"]=self.validation_error
   return self._degraded(memory,"invalid_understanding:"+self.validation_error)
