from __future__ import annotations
from dataclasses import dataclass,asdict
import json
from .escalation_contract import BY_KEY
SCHEMA={"type":"object","properties":{"turn_role":{"type":"string","enum":["field_value","unknown_value","correction","independent_question","workflow_action","ambiguous"]},"workflow_action":{"type":"string","enum":["none","cancel","suspend","resume","confirm","restart"]},"field":{"type":["string","null"]},"value":{"type":["string","null"]},"confidence":{"type":"number"},"reason":{"type":"string"}},"required":["turn_role","workflow_action","field","value","confidence","reason"]}
SYSTEM="""Classify one turn inside an existing support escalation workflow. Interpret meaning from workflow state, pending question, collected fields and the user message. Do not use product-specific assumptions. Lifecycle actions outrank field capture. A request to stop is cancel. A temporary unrelated technical or conceptual question is independent_question. A request to continue a suspended process is resume. A request to start again after cancellation is restart. Confirmation is valid only in review. Correction must identify the canonical field and corrected value. A direct factual answer, including a short proper name, identifier, version, location or scope, is field_value only when it answers the pending question. unknown_value means the requested information is unavailable. If the turn cannot be assigned safely, use ambiguous. Return only the schema JSON."""
@dataclass
class WorkflowUnderstanding:
 turn_role:str="ambiguous";workflow_action:str="none";field:str|None=None;value:str|None=None;confidence:float=0.;reason:str=""
 def to_dict(self):return asdict(self)
class WorkflowInterpreter:
 def __init__(self,gateway,max_tokens=180):self.gateway=gateway;self.max_tokens=max(120,min(240,int(max_tokens)));self.last_provider_result={};self.contract_valid=False
 def interpret(self,message,state):
  from app.llm_gateway.models import LLMRequest
  pending=state.pending_field;spec=BY_KEY.get(pending)
  payload={"workflow_status":state.status,"pending_field":pending,"pending_question":spec.question if spec else None,"collected_fields":{k:(v or {}).get("value") for k,v in state.fields.items()},"user_message":message}
  r=self.gateway.complete(LLMRequest([{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_clean_workflow_understanding",self.max_tokens,0.,SCHEMA));self.last_provider_result=r.to_dict();self.contract_valid=False
  if not r.ok:return WorkflowUnderstanding(reason="provider_unavailable")
  try:
   raw=json.loads(str(r.text or "").strip());role=str(raw.get("turn_role") or "ambiguous");action=str(raw.get("workflow_action") or "none");field=raw.get("field");value=raw.get("value");confidence=float(raw.get("confidence") or 0);reason=str(raw.get("reason") or "")
   if role not in {"field_value","unknown_value","correction","independent_question","workflow_action","ambiguous"}:raise ValueError("invalid_role")
   if action not in {"none","cancel","suspend","resume","confirm","restart"}:raise ValueError("invalid_action")
   if role=="field_value":field=pending;value=str(value or message).strip()
   if role=="unknown_value":field=pending;value=None
   self.contract_valid=True;return WorkflowUnderstanding(role,action,field,value,confidence,reason)
  except Exception:return WorkflowUnderstanding(reason="invalid_contract")
