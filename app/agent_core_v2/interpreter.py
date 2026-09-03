from __future__ import annotations
import json,re
from .models import InterpreterProposal
ALLOWED_INTENTS={"social","capabilities","support_intake","conceptual","procedural","troubleshooting","requirements","architecture","warranty","escalation","cancel","resume","out_of_scope","unknown"}
ALLOWED_ACTIONS={"respond_directly","ask_clarification","retrieve","record_case_detail","record_attempt","record_attempt_result","start_escalation","continue_escalation","suspend_escalation","resume_escalation","cancel_all","out_of_scope"}
ALLOWED_RELATIONS={"same_topic","new_topic","independent_question","unknown"}
ALLOWED_ENTITY_KINDS={"product","component","process"}
PROPOSAL_FIELDS=("conversation_act","intent","requested_action","topic_relation","entities","facts","clarification_question","confidence","reasoning_summary")
GENERIC_ENTITY_TERMS={"equipo","equipos","usuario","usuarios","mensaje","mensajes","sistema","sistemas","información","informacion","dispositivo","dispositivos"}
PROBLEM_PATTERNS=(r"\berror\b",r"\bfalla",r"\bdejó\s+de\b",r"\bdejo\s+de\b",r"\bno\s+(?:puedo|funciona|carga|abre|aparece|reporta|imprime|accede|responde)",r"\bdesapare",r"\bbloque",r"\brechaza",r"\btimeout\b",r"\btiempo\s+de\s+espera\b")
PROCEDURAL_PATTERNS=(r"\b(?:cómo|como)\s+(?:puedo|hago|configuro|creo|asigno|instalo|habilito)\b",r"\bnecesito\s+(?:crear|configurar|asignar|instalar|habilitar)\b",r"\bquiero\s+(?:crear|configurar|asignar|instalar|habilitar)\b")
NEXT_STEP_PATTERNS=(r"\bqué\s+(?:puedo|debo)\s+(?:validar|hacer|revisar)\b",r"\bcuál\s+es\s+el\s+siguiente\s+paso\b",r"\bqué\s+sigue\b")
DETAIL_PATTERNS=(r"\b(?:comenzó|inicio|inició)\b",r"\besta\s+mañana\b",r"\bno\s+(?:hemos|se\s+han)\s+(?:realizado|hecho)\s+cambios\b",r"\bdesde\s+(?:ayer|hoy|esta)\b")
SCOPE_PATTERNS=(r"\bvarios\s+equipos\b",r"\bmúltiples\s+equipos\b",r"\btodos\s+los\s+equipos\b",r"\bvarios\s+usuarios\b",r"\btodos\s+los\s+usuarios\b",r"\btoda\s+la\s+sede\b")
SCHEMA={"type":"object","properties":{"conversation_act":{"type":"string"},"intent":{"type":"string","enum":sorted(ALLOWED_INTENTS)},"requested_action":{"type":"string","enum":sorted(ALLOWED_ACTIONS)},"topic_relation":{"type":"string","enum":sorted(ALLOWED_RELATIONS)},"entities":{"type":"array","items":{"type":"object"}},"facts":{"type":"array","items":{"type":"object"}},"clarification_question":{"type":["string","null"]},"confidence":{"type":"number"},"reasoning_summary":{"type":"string"}},"required":list(PROPOSAL_FIELDS)}
def _matches(patterns,text):return any(re.search(p,text,re.I) for p in patterns)
def _clean(v):return re.sub(r"\s+"," ",str(v or "")).strip(" .¿?")
def _id(v):return re.sub(r"[^a-z0-9]+","_",str(v).casefold()).strip("_")
def _extract(t):
 t=str(t or "").strip();a=t.find("{");b=t.rfind("}")
 if a<0 or b<a:raise ValueError("incomplete_json")
 return json.loads(t[a:b+1])
def _project(d):return {k:d.get(k) for k in PROPOSAL_FIELDS}
def _state_values(state):
 if state is None:return set(),set()
 try:
  products={str(x.canonical_id) for x in state.active_topic.products};symptoms={_clean(x).casefold() for x in state.technical_case.symptoms};return products,symptoms
 except Exception:return set(),set()
def _fallback(message,state,reason):
 text=_clean(message);low=text.casefold();products,_=_state_values(state);same=bool(products)
 if _matches(NEXT_STEP_PATTERNS,low):return InterpreterProposal("request_next_step","troubleshooting","retrieve","same_topic" if same else "unknown",[],[],None,.85,f"fallback:{reason}:next_step")
 if _matches(DETAIL_PATTERNS,low):
  facts=[]
  if re.search(r"\b(?:comenzó|inicio|inició|mañana|ayer|hoy)\b",low):facts.append({"type":"timeline","value":text,"confidence":.8,"source":"deterministic_fallback"})
  if "cambios" in low:facts.append({"type":"change_context","value":"No se informan cambios previos","confidence":.8,"source":"deterministic_fallback"})
  return InterpreterProposal("provide_case_detail","troubleshooting","record_case_detail","same_topic" if same else "unknown",[],facts,None,.8,f"fallback:{reason}:case_detail")
 return InterpreterProposal("clarify","troubleshooting" if same else "unknown","ask_clarification","same_topic" if same else "unknown",[],[],"¿Puedes precisar qué resultado esperas o qué mensaje aparece?",.65,f"fallback:{reason}:clarification")
def normalize_payload(raw,message="",state=None):
 raw=dict(raw or {});text=_clean(message);low=text.casefold();confidence=float(raw.get("confidence",0) or 0);existing_products,existing_symptoms=_state_values(state)
 relation=str(raw.get("topic_relation") or "unknown");relation={"related":"same_topic","same":"same_topic","new":"new_topic"}.get(relation,relation)
 intent={"troubleshoot":"troubleshooting","procedure":"procedural"}.get(str(raw.get("intent") or "unknown"),str(raw.get("intent") or "unknown"));action=str(raw.get("requested_action") or "ask_clarification");act=str(raw.get("conversation_act") or "unknown")
 if _matches(PROBLEM_PATTERNS,low):intent="troubleshooting";action="retrieve";act="troubleshooting"
 elif _matches(NEXT_STEP_PATTERNS,low) and existing_products:intent="troubleshooting";action="retrieve";act="request_next_step";relation="same_topic"
 elif _matches(DETAIL_PATTERNS,low) and existing_products and "?" not in text:
  intent="troubleshooting";action="record_case_detail";act="provide_case_detail";relation="same_topic"
 elif _matches(PROCEDURAL_PATTERNS,low) and not _matches(PROBLEM_PATTERNS,low):intent="procedural";action="retrieve";act="request_procedure"
 if intent not in ALLOWED_INTENTS:intent="unknown"
 if action not in ALLOWED_ACTIONS:action="ask_clarification"
 if relation not in ALLOWED_RELATIONS:relation="unknown"
 entities=[]
 for x in raw.get("entities") or []:
  if not isinstance(x,dict):continue
  kind=str(x.get("kind") or x.get("type") or "product");name=_clean(x.get("canonical_name") or x.get("name") or x.get("text") or x.get("value"));matched=_clean(x.get("matched_text") or x.get("text") or name)
  if kind not in ALLOWED_ENTITY_KINDS or not name:continue
  if kind!="product" and matched.casefold() in GENERIC_ENTITY_TERMS:continue
  cid=str(x.get("canonical_id") or x.get("id") or _id(name))
  if relation=="same_topic" and cid in existing_products:continue
  entities.append({"kind":kind,"canonical_id":cid,"canonical_name":name,"matched_text":matched,"confidence":float(x.get("confidence",confidence or .7))})
 facts=[]
 for x in raw.get("facts") or []:
  if not isinstance(x,dict):continue
  typ=str(x.get("type") or x.get("key") or "technical_context");value=_clean(x.get("value") or x.get("fact") or x.get("name"))
  if not value:continue
  if typ in {"scope","impact","affected"}:typ="affected_scope"
  if relation=="same_topic" and typ=="symptom" and value.casefold() in existing_symptoms:continue
  facts.append({"type":typ,"value":value,"confidence":float(x.get("confidence",confidence or .7)),"source":"interpreter_normalized"})
 if intent=="troubleshooting" and _matches(PROBLEM_PATTERNS,low) and not any(x["type"]=="symptom" for x in facts):facts.append({"type":"symptom","value":text,"confidence":.8,"source":"message_fallback"})
 for p in SCOPE_PATTERNS:
  m=re.search(p,text,re.I)
  if m and not any(x["type"]=="affected_scope" for x in facts):facts.append({"type":"affected_scope","value":m.group(0),"confidence":.9,"source":"scope_fallback"});break
 if action=="record_case_detail":
  if re.search(r"\b(?:comenzó|inicio|inició|mañana|ayer|hoy)\b",low) and not any(x["type"]=="timeline" for x in facts):facts.append({"type":"timeline","value":text,"confidence":.8,"source":"detail_fallback"})
  if "cambios" in low and not any(x["type"]=="change_context" for x in facts):facts.append({"type":"change_context","value":"No se informan cambios previos","confidence":.8,"source":"detail_fallback"})
 result={"conversation_act":act,"intent":intent,"requested_action":action,"topic_relation":relation,"entities":entities,"facts":facts,"clarification_question":raw.get("clarification_question") if action=="ask_clarification" else None,"confidence":confidence,"reasoning_summary":str(raw.get("reasoning_summary") or "")[:120]}
 return _project(result)
class QwenInterpreter:
 def __init__(self,gateway,max_tokens=220):self.gateway=gateway;self.max_tokens=max(220,min(280,int(max_tokens)))
 def interpret(self,message,state):
  from app.llm_gateway.models import LLMRequest
  system="""Classify one printing-support turn as compact JSON. Return only deltas: do not repeat entities or facts already in state unless corrected. Generic words such as devices, users, messages, systems, or information are not components. A statement adding time or no-change context is record_case_detail without retrieval. A request for the next validation is request_next_step with retrieve. Keep reasoning_summary under 8 words."""
  payload=json.dumps({"message":message,"state":state.to_dict()},ensure_ascii=False,separators=(",",":"));r=self.gateway.complete(LLMRequest([{"role":"system","content":system},{"role":"user","content":payload}],"agent_core_v2_interpreter",self.max_tokens,0.,SCHEMA))
  if not r.ok:return _fallback(message,state,"provider_error")
  if r.finish_reason=="length":return _fallback(message,state,"truncated")
  try:return InterpreterProposal(**normalize_payload(_extract(r.text),message,state))
  except Exception:return _fallback(message,state,"invalid_output")
class ScriptedInterpreter:
 def __init__(self,outputs):self.outputs=list(outputs);self.i=0
 def interpret(self,message,state):r=self.outputs[self.i];self.i+=1;return InterpreterProposal(**normalize_payload(r,message,state))
