from __future__ import annotations
import json
from .contracts import UNDERSTANDING_SCHEMA
from .models import TurnUnderstanding
from .memory import compact_context

SYSTEM="""You are the semantic understanding layer for an enterprise printing support assistant. Interpret the current user message together with memory and the assistant's last question. Preserve and enrich an unfinished goal: a short answer adds missing detail and never replaces the goal. Distinguish a how-to request from a reported failure. A failed, blocked, missing or unavailable operation is troubleshooting and must create a symptom or observation. A self-contained unrelated knowledge request is independent and out_of_scope; do not attach it to the active printing topic. Ask clarification only when one missing detail materially changes the next helpful action. No product-specific keyword rules. Return compact JSON only."""

def _safe(memory,message,reason):
 goal=memory.pending_goal.summary or message
 return TurnUnderstanding("follow_up" if memory.pending_goal.status=="active" else "new_request","unknown","same_topic","uncertain",goal,False,{},[],True,"the specific outcome needed",False,.2,reason)

class ConversationUnderstanding:
 def __init__(self,gateway,max_tokens=360):self.gateway=gateway;self.max_tokens=max(280,int(max_tokens));self.last_provider_result={}
 def interpret(self,message,memory):
  from app.llm_gateway.models import LLMRequest
  payload={"current_message":message,"memory":compact_context(memory)}
  r=self.gateway.complete(LLMRequest([{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_clean_understanding",self.max_tokens,0.,UNDERSTANDING_SCHEMA));self.last_provider_result=r.to_dict()
  if not r.ok:return _safe(memory,message,"provider_error")
  try:
   raw=json.loads(r.text[r.text.find('{'):r.text.rfind('}')+1])
   return TurnUnderstanding(**raw)
  except Exception:return _safe(memory,message,"invalid_understanding")
