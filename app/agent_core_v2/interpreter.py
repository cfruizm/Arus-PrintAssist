from __future__ import annotations
import json,re
from .models import InterpreterProposal
ALLOWED_INTENTS={"social","capabilities","support_intake","conceptual","procedural","troubleshooting","requirements","architecture","warranty","escalation","cancel","resume","out_of_scope","unknown"}
ALLOWED_ACTIONS={"respond_directly","ask_clarification","retrieve","record_case_detail","record_attempt","record_attempt_result","start_escalation","continue_escalation","suspend_escalation","resume_escalation","cancel_all","out_of_scope"}
ALLOWED_RELATIONS={"same_topic","new_topic","independent_question","unknown"}
ALLOWED_ENTITY_KINDS={"product","component","process"}
PROCEDURAL_PATTERNS=(r"\b(?:cómo|como)\s+(?:puedo|hago|configuro|creo|asigno|instalo|habilito)\b",r"\bnecesito\s+(?:crear|configurar|asignar|instalar|habilitar)\b",r"\bquiero\s+(?:crear|configurar|asignar|instalar|habilitar)\b",r"\bpasos\s+para\b",r"\bindícame\s+(?:los\s+)?pasos\b")
PROBLEM_PATTERNS=(r"\berror\b",r"\bfalla",r"\bdejó\s+de\b",r"\bdejo\s+de\b",r"\bno\s+(?:puedo|funciona|carga|abre|aparece|reporta|imprime|accede|responde)",r"\bdesapare",r"\bbloque",r"\brechaza",r"\btimeout\b",r"\btiempo\s+de\s+espera\b",r"\bintermiten")
SCOPE_PATTERNS=(r"\bvarios\s+equipos\b",r"\bmúltiples\s+equipos\b",r"\bmultiples\s+equipos\b",r"\btodos\s+los\s+equipos\b",r"\bun\s+equipo\b",r"\bvarios\s+usuarios\b",r"\btodos\s+los\s+usuarios\b",r"\bun\s+usuario\b",r"\btoda\s+la\s+sede\b")
SCHEMA={"type":"object","properties":{"conversation_act":{"type":"string"},"intent":{"type":"string","enum":sorted(ALLOWED_INTENTS)},"requested_action":{"type":"string","enum":sorted(ALLOWED_ACTIONS)},"topic_relation":{"type":"string","enum":sorted(ALLOWED_RELATIONS)},"entities":{"type":"array","items":{"type":"object"}},"facts":{"type":"array","items":{"type":"object"}},"clarification_question":{"type":["string","null"]},"confidence":{"type":"number"},"reasoning_summary":{"type":"string"}},"required":["conversation_act","intent","requested_action","topic_relation","entities","facts","clarification_question","confidence","reasoning_summary"]}
INTENT_ALIASES={"troubleshoot_access":"troubleshooting","troubleshoot":"troubleshooting","procedure":"procedural","concept":"conceptual"};RELATION_ALIASES={"related":"same_topic","same":"same_topic","new":"new_topic"}
INTERPRETER_PROPOSAL_FIELDS=("conversation_act","intent","requested_action","topic_relation","entities","facts","clarification_question","confidence","reasoning_summary")

def project_interpreter_payload(payload):
 return {field:payload.get(field) for field in INTERPRETER_PROPOSAL_FIELDS}

def ignored_interpreter_fields(payload):
 return sorted(set(payload or {})-set(INTERPRETER_PROPOSAL_FIELDS))
def _matches(patterns,text):return any(re.search(p,text,re.I) for p in patterns)
def _extract(t):
 t=str(t or "").strip();a=t.find("{");b=t.rfind("}")
 if a<0 or b<a:raise ValueError("The model did not return a complete JSON object")
 return json.loads(t[a:b+1])
def _id(v):return re.sub(r"[^a-z0-9]+","_",str(v).casefold()).strip("_")
def _clean(v):return re.sub(r"\s+"," ",str(v or "")).strip(" .¿?")
def _symptom(message):
 text=_clean(message);text=re.sub(r"(?i)\s*[¿?]*(qué|que|cuál|cual|cómo|como)\s+(?:debo\s+)?(?:validar|hacer|revisar|verificar)|¿qué\s+validaciones\s+corresponden\??.*$","",text).strip(" .¿?");return text[:300]
def _scope(message):
 text=_clean(message)
 for p in SCOPE_PATTERNS:
  m=re.search(p,text,re.I)
  if m:return m.group(0)
 return ""
def normalize_payload(raw,message=""):
 raw=dict(raw or {});text=str(message or "").casefold();confidence=float(raw.get("confidence",0) or 0);has_problem=_matches(PROBLEM_PATTERNS,text);has_procedure=_matches(PROCEDURAL_PATTERNS,text)
 raw["intent"]=INTENT_ALIASES.get(str(raw.get("intent") or ""),str(raw.get("intent") or "unknown"));raw["topic_relation"]=RELATION_ALIASES.get(str(raw.get("topic_relation") or ""),str(raw.get("topic_relation") or "unknown"))
 if has_problem:raw["intent"]="troubleshooting";raw["requested_action"]="retrieve";raw["conversation_act"]="troubleshooting";raw["clarification_question"]=None
 elif has_procedure:raw["intent"]="procedural";raw["requested_action"]="retrieve";raw["conversation_act"]="request_procedure";raw["clarification_question"]=None
 if raw["intent"] not in ALLOWED_INTENTS:raw["intent"]="unknown"
 if raw.get("requested_action") not in ALLOWED_ACTIONS:raw["requested_action"]="ask_clarification"
 if raw["topic_relation"] not in ALLOWED_RELATIONS:raw["topic_relation"]="unknown"
 entities=[];facts=[]
 for x in raw.get("entities") or []:
  if not isinstance(x,dict):continue
  kind=str(x.get("kind") or x.get("type") or "product");name=str(x.get("canonical_name") or x.get("name") or x.get("text") or x.get("value") or "").strip()
  if kind in ALLOWED_ENTITY_KINDS and name:entities.append({"kind":kind,"canonical_id":str(x.get("canonical_id") or x.get("id") or _id(name)),"canonical_name":name,"matched_text":str(x.get("matched_text") or x.get("mention") or x.get("text") or name),"confidence":float(x.get("confidence",confidence or .7))})
 raw["entities"]=entities
 for x in raw.get("facts") or []:
  if not isinstance(x,dict):continue
  typ=str(x.get("type") or x.get("kind") or x.get("key") or "technical_context");value=x.get("value") if "value" in x else x.get("fact") or x.get("name")
  if isinstance(value,dict):value=value.get("description") or json.dumps(value,ensure_ascii=False)
  value=_clean(value)
  if not value:continue
  low=value.casefold()
  if typ=="technical_context" and _matches(SCOPE_PATTERNS,low):typ="affected_scope"
  elif typ in {"technical_context","symptom","error"} and _matches(PROBLEM_PATTERNS,low):typ="symptom"
  elif typ in {"scope","impact","affected"}:typ="affected_scope"
  facts.append({"type":typ,"value":value,"confidence":float(x.get("confidence",confidence or .7)),"source":"interpreter_normalized"})
 if raw["intent"]=="troubleshooting":
  if not any(x["type"]=="symptom" for x in facts):facts.append({"type":"symptom","value":_symptom(message),"confidence":min(confidence or .75,.85),"source":"deterministic_message_fallback"})
  scope=_scope(message)
  if scope and not any(x["type"]=="affected_scope" for x in facts):facts.append({"type":"affected_scope","value":scope,"confidence":.9,"source":"deterministic_scope_fallback"})
 raw["facts"]=facts;raw["conversation_act"]=str(raw.get("conversation_act") or "unknown");raw["clarification_question"]=raw.get("clarification_question");raw["confidence"]=confidence;raw["reasoning_summary"]=str(raw.get("reasoning_summary") or "")[:160]
 return raw
class QwenInterpreter:
 def __init__(self,gateway,max_tokens=220):self.gateway=gateway;self.max_tokens=max(240,min(320,int(max_tokens)))
 def interpret(self,message,state):
  from app.llm_gateway.models import LLMRequest
  system="Classify one printing-support turn. Return compact JSON only. Failure or lost-function signals always mean troubleshooting, even when the user asks what to validate. Put malfunction in facts type symptom and impact in affected_scope. Entity kinds only product, component, process. Do not answer technically."
  payload=json.dumps({"message":message,"state":state.to_dict()},ensure_ascii=False,separators=(",",":"));r=self.gateway.complete(LLMRequest([{"role":"system","content":system},{"role":"user","content":payload}],"agent_core_v2_interpreter",self.max_tokens,0.,SCHEMA))
  if not r.ok:raise RuntimeError(r.error_message or "interpreter_provider_failed")
  if r.finish_reason=="length":raise ValueError("Interpreter output was truncated")
  normalized=normalize_payload(_extract(r.text),message);return InterpreterProposal(**project_interpreter_payload(normalized))
class ScriptedInterpreter:
 def __init__(self,outputs):self.outputs=list(outputs);self.i=0
 def interpret(self,message,state):r=self.outputs[self.i];self.i+=1;normalized=normalize_payload(r,message);return InterpreterProposal(**project_interpreter_payload(normalized))
