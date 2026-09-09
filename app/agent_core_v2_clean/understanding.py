import json
from .contracts import UNDERSTANDING_SCHEMA
from .models import TurnUnderstanding
from .memory import compact_context
SYSTEM="""Semantic understanding for an enterprise printing-support assistant. The supported domain includes printing software, print-management platforms, fleet-management tools, printers, MFDs, scanning, accounting, consumables, installation, connectivity and related operational processes. A new printing product is in_scope even if unrelated to the previous product. Interpret the current message with memory and the last assistant question. A short answer completes the pending question and never replaces the goal. Do not classify a request for help as a failure unless an actual malfunction is reported. Distinguish how-to from failure. Preserve known details. A genuinely unrelated self-contained request is independent and out_of_scope. Ask only for a detail that materially changes the next action. Do not invent relationships or accuse the user of confusion. Return compact JSON only."""
class ConversationUnderstanding:
 def __init__(self,gateway,max_tokens=300):self.gateway=gateway;self.max_tokens=max(240,int(max_tokens));self.last_provider_result={}
 def _degraded(self,message,memory,reason):
  active=memory.pending_goal.summary or memory.active_topic or message;is_answer=bool(memory.last_assistant_question)
  updates={"latest_user_reply":message}
  case=[]
  if memory.support_case.status=="diagnosing":case=[{"type":"observation","value":message}]
  return TurnUnderstanding("answer_to_question" if is_answer else "follow_up",memory.pending_goal.intent or "unknown","same_topic","in_scope",active,False,updates,case,False,None,False,.25,reason,True)
 def interpret(self,message,memory):
  from app.llm_gateway.models import LLMRequest
  r=self.gateway.complete(LLMRequest([{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps({"current_message":message,"memory":compact_context(memory)},ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_clean_understanding",self.max_tokens,0.,UNDERSTANDING_SCHEMA));self.last_provider_result=r.to_dict()
  if not r.ok:return self._degraded(message,memory,"provider_error:"+str(r.error_code or "unknown"))
  try:
   raw=json.loads(r.text[r.text.find('{'):r.text.rfind('}')+1]);return TurnUnderstanding(**raw)
  except Exception:return self._degraded(message,memory,"invalid_understanding")
