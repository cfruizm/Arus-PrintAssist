from __future__ import annotations
import json,re
from .models import InterpreterProposal
ALLOWED_INTENTS={"social","capabilities","support_intake","conceptual","procedural","troubleshooting","requirements","architecture","warranty","escalation","cancel","resume","out_of_scope","unknown"}
ALLOWED_ACTIONS={"respond_directly","ask_clarification","retrieve","record_case_detail","record_attempt","record_attempt_result","start_escalation","continue_escalation","suspend_escalation","resume_escalation","cancel_all","out_of_scope"}
ALLOWED_RELATIONS={"same_topic","new_topic","independent_question","unknown"}
ALLOWED_ENTITY_KINDS={"product","component","process"}
PROCEDURAL_PATTERNS=(r"\b(?:cómo|como)\s+(?:puedo|hago|configuro|creo|asigno|instalo|habilito)\b",r"\bnecesito\s+(?:crear|configurar|asignar|instalar|habilitar)\b",r"\bquiero\s+(?:crear|configurar|asignar|instalar|habilitar)\b",r"\bpasos\s+para\b",r"\bindícame\s+(?:los\s+)?pasos\b")
PROBLEM_PATTERNS=(r"\berror\b",r"\bfalla",r"\bno\s+(?:puedo|funciona|carga|abre|aparece|reporta|imprime|accede)",r"\bdesapare",r"\bbloque",r"\brechaza",r"\btimeout\b",r"\btiempo\s+de\s+espera\b")
SCHEMA={"type":"object","properties":{"conversation_act":{"type":"string"},"intent":{"type":"string","enum":sorted(ALLOWED_INTENTS)},"requested_action":{"type":"string","enum":sorted(ALLOWED_ACTIONS)},"topic_relation":{"type":"string","enum":sorted(ALLOWED_RELATIONS)},"entities":{"type":"array","items":{"type":"object"}},"facts":{"type":"array","items":{"type":"object"}},"clarification_question":{"type":["string","null"]},"confidence":{"type":"number"},"reasoning_summary":{"type":"string"}},"required":["conversation_act","intent","requested_action","topic_relation","entities","facts","clarification_question","confidence","reasoning_summary"]}
INTENT_ALIASES={"troubleshoot_access":"troubleshooting","troubleshoot":"troubleshooting","procedure":"procedural","concept":"conceptual"};RELATION_ALIASES={"related":"same_topic","same":"same_topic","new":"new_topic"}
def _extract(t):
 t=str(t or "").strip();a=t.find("{");b=t.rfind("}")
 if a<0 or b<a:raise ValueError("The model did not return a complete JSON object")
 return json.loads(t[a:b+1])
def _id(v):return re.sub(r"[^a-z0-9]+","_",str(v).casefold()).strip("_")
def _matches(patterns,text):return any(re.search(p,text,re.I) for p in patterns)
def _symptom_from_message(message):
 text=re.sub(r"\s+"," ",str(message or "")).strip();text=re.sub(r"(?i)\s*[¿?]*(qué|que|cuál|cual|cómo|como)\s+debo\s+(validar|hacer).*$","",text).strip(" .¿?");return text[:300]
def normalize_payload(raw,message=""):
 raw=dict(raw or {});text=str(message or "").casefold();confidence=float(raw.get("confidence",0) or 0)
 raw["intent"]=INTENT_ALIASES.get(str(raw.get("intent") or ""),str(raw.get("intent") or "unknown"));raw["topic_relation"]=RELATION_ALIASES.get(str(raw.get("topic_relation") or ""),str(raw.get("topic_relation") or "unknown"))
 # Linguistic intent is a transversal validator, not a product rule.
 if _matches(PROCEDURAL_PATTERNS,text) and not _matches(PROBLEM_PATTERNS,text):
  raw["intent"]="procedural";raw["requested_action"]="retrieve";raw["conversation_act"]="request_procedure";raw["clarification_question"]=None
 if raw["intent"] not in ALLOWED_INTENTS:raw["intent"]="unknown"
 if raw.get("requested_action") not in ALLOWED_ACTIONS:raw["requested_action"]="ask_clarification"
 if raw["topic_relation"] not in ALLOWED_RELATIONS:raw["topic_relation"]="unknown"
 entities=[];facts=[]
 for x in raw.get("entities") or []:
  if not isinstance(x,dict):continue
  kind=str(x.get("kind") or x.get("type") or "product")
  name=str(x.get("canonical_name") or x.get("name") or x.get("value") or "").strip()
  if kind in ALLOWED_ENTITY_KINDS and name:entities.append({"kind":kind,"canonical_id":str(x.get("canonical_id") or x.get("id") or _id(name)),"canonical_name":name,"matched_text":str(x.get("matched_text") or x.get("mention") or name),"confidence":float(x.get("confidence",confidence or .7))})
  elif kind in {"symptom","error","technical_context"} and name:facts.append({"type":"symptom" if kind in {"symptom","error"} else kind,"value":name,"confidence":float(x.get("confidence",confidence or .7))})
 raw["entities"]=entities
 for x in raw.get("facts") or []:
  if isinstance(x,str):facts.append({"type":"symptom","value":x,"confidence":confidence or .7})
  elif isinstance(x,dict):
   value=x.get("value") if "value" in x else x.get("name")
   if isinstance(value,dict):value=value.get("description") or json.dumps(value,ensure_ascii=False)
   if str(value or "").strip():facts.append({"type":str(x.get("type") or "technical_context"),"value":str(value),"confidence":float(x.get("confidence",confidence or .7))})
 if raw["intent"]=="troubleshooting" and _matches(PROBLEM_PATTERNS,text) and not any(x.get("type")=="symptom" for x in facts):facts.append({"type":"symptom","value":_symptom_from_message(message),"confidence":min(confidence or .75,.85),"source":"deterministic_message_fallback"})
 raw["facts"]=facts;raw["conversation_act"]=str(raw.get("conversation_act") or "unknown");raw["clarification_question"]=raw.get("clarification_question");raw["confidence"]=confidence;raw["reasoning_summary"]=str(raw.get("reasoning_summary") or "")[:160]
 return raw
class QwenInterpreter:
 def __init__(self,gateway,max_tokens=220):self.gateway=gateway;self.max_tokens=max(240,min(320,int(max_tokens)))
 def interpret(self,message,state):
  from app.llm_gateway.models import LLMRequest
  system="""Classify one printing-support turn. Return compact JSON only. Use schema enums. Entity kinds only product, component, process. Put symptoms in facts, never entities. A request to create, configure, assign, install or enable something is procedural unless it reports a failure. If product and symptom are present and user asks what to validate, retrieve. Do not answer technically. reasoning_summary max 12 words."""
  payload=json.dumps({"message":message,"state":state.to_dict()},ensure_ascii=False,separators=(",",":"));r=self.gateway.complete(LLMRequest([{"role":"system","content":system},{"role":"user","content":payload}],"agent_core_v2_interpreter",self.max_tokens,0.,SCHEMA))
  if not r.ok:raise RuntimeError(r.error_message or "interpreter_provider_failed")
  if r.finish_reason=="length":raise ValueError("Interpreter output was truncated")
  return InterpreterProposal(**normalize_payload(_extract(r.text),message))
class ScriptedInterpreter:
 def __init__(self,outputs):self.outputs=list(outputs);self.i=0
 def interpret(self,message,state):r=self.outputs[self.i];self.i+=1;return InterpreterProposal(**normalize_payload(r,message))
