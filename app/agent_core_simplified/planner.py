from __future__ import annotations
import json
from .models import TurnPlan
PLAN_SCHEMA={"type":"object","properties":{"topic_relation":{"type":"string","enum":["same","new","previous"]},"entities":{"type":"array","items":{"type":"object"}},"symptoms":{"type":"array","items":{"type":"string"}},"details":{"type":"array","items":{"type":"object"}},"attempt":{"type":["string","null"]},"attempt_result":{"type":["string","null"]},"request_kind":{"type":"string","enum":["none","answer","procedure","troubleshoot","requirements","architecture","warranty","escalate","cancel","out_of_scope"]},"needs_documents":{"type":"boolean"},"escalation_action":{"type":"string","enum":["none","start","continue","finish","cancel"]},"confidence":{"type":"number"}},"required":["topic_relation","entities","symptoms","details","attempt","attempt_result","request_kind","needs_documents","escalation_action","confidence"]}
ALLOWED_DETAILS={"scope","timeline","change_context","environment","error_message","version","location","frequency","observed_behavior","expected_behavior","contact","asset","evidence"}
def _extract(text):
 text=str(text or "").strip();a=text.find("{");b=text.rfind("}")
 if a<0 or b<a:raise ValueError("planner_json_incomplete")
 return json.loads(text[a:b+1])
def normalize(raw):
 r=dict(raw or {});entities=[]
 for x in r.get("entities") or []:
  if isinstance(x,dict) and str(x.get("name") or x.get("canonical_name") or "").strip():entities.append({"kind":str(x.get("kind") or "product"),"canonical_id":str(x.get("canonical_id") or ""),"name":str(x.get("name") or x.get("canonical_name")),"mention":str(x.get("mention") or x.get("matched_text") or x.get("name") or x.get("canonical_name")),"confidence":float(x.get("confidence",r.get("confidence",0)) or 0)})
 details=[]
 for x in r.get("details") or []:
  if isinstance(x,dict) and str(x.get("value") or "").strip():details.append({"type":str(x.get("type") or "detail") if str(x.get("type") or "") in ALLOWED_DETAILS else "detail","value":str(x.get("value"))})
 kind=str(r.get("request_kind") or "none");relation=str(r.get("topic_relation") or "same");esc=str(r.get("escalation_action") or "none")
 if kind not in {"none","answer","procedure","troubleshoot","requirements","architecture","warranty","escalate","cancel","out_of_scope"}:kind="none"
 if relation not in {"same","new","previous"}:relation="same"
 if esc not in {"none","start","continue","finish","cancel"}:esc="none"
 return TurnPlan(relation,entities,[str(x) for x in r.get("symptoms") or [] if str(x).strip()],details,str(r.get("attempt")) if r.get("attempt") else None,str(r.get("attempt_result")) if r.get("attempt_result") else None,kind,bool(r.get("needs_documents")),esc,float(r.get("confidence",0) or 0))
class Planner:
 def __init__(self,gateway,max_tokens=260):self.gateway=gateway;self.max_tokens=max_tokens
 def plan(self,message,state):
  from app.llm_gateway.models import LLMRequest
  system="""Plan one printing-support turn as independent axes. Do not force one label to represent the whole message. Extract only new or corrected information relative to state. attempt is an action already performed; attempt_result is its outcome. request_kind describes what the user wants now. needs_documents is true only when answering requires product documentation. escalation_action manages escalation. Do not answer the user. Do not repeat existing facts. Return compact JSON only."""
  payload={"message":message,"state":state.to_dict()};res=self.gateway.complete(LLMRequest([{"role":"system","content":system},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_simplified_planner",self.max_tokens,0.,PLAN_SCHEMA))
  if not res.ok or res.finish_reason=="length":return TurnPlan(confidence=0)
  try:return normalize(_extract(res.text))
  except Exception:return TurnPlan(confidence=0)
