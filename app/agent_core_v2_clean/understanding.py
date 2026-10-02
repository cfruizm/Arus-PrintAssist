import json
from .contracts import UNDERSTANDING_SCHEMA
from .models import TurnUnderstanding
from .memory import compact_context,normalize_goal_updates
SYSTEM="""Semantic understanding for an enterprise printing-support assistant. Interpret the current message using memory and the last assistant question. The current_goal must express the current request, not copy an earlier operation. Distinguish conceptual, procedural, requirements and troubleshooting. Use requirements for prerequisites, compatibility, constraints or conditions; use procedural for execution steps. A changed operation about the same subject refines the goal and remains same_topic. request_elaboration is valid only when the message depends on an active goal or last assistant question. answer_to_question supplies requested information. Put symptoms and diagnostic facts in case_updates. Clarify only when one missing fact is indispensable. A clear conceptual request never needs clarification. Return one complete JSON object matching the schema. No fields outside the schema. Extract canonical_subject as the product, platform, component or technical entity governing the request. Never copy the full request. subject_origin is current_message only when explicit, otherwise conversation_memory. reference_relation is previous_subject when returning to the previously active entity, current_subject when referring to the active entity, otherwise none. A changed operation does not change canonical_subject. An explicit different subject creates new_topic. Keep reasoning_summary under 20 words. requested_workflow is an independent operational workflow contract. Use start_escalation only when the user actually requests transfer or escalation of the current support case. A conceptual question about escalation, a request to explain escalation, or generic mention of escalation must use none. A permission or availability question about starting another consultation is social: use user_act social, intent social, should_retrieve false, no canonical_subject, and requested_workflow none. Use cancel_escalation, suspend_escalation, resume_escalation or confirm_escalation only when the user requests that lifecycle action. Do not infer workflow actions from technical intent alone. When a troubleshooting message contains completed validations and an observed outcome, preserve the full cardinality of the user report: identify every semantically distinct completed action and emit one attempted_action case update for each action. If one observed result applies to several completed actions, copy that result and its outcome to every corresponding attempted_action. If the actions cannot be separated responsibly, preserve them together as one compound attempted_action instead of omitting any action. Never collapse several confirmed actions into only the last action. For each attempted_action, value is the complete action, result is the observed result, and outcome is resolved, improved, unchanged, worsened or unknown. Execution of an action is not a successful outcome. If the failure continues, outcome is unchanged. When an active support case exists and a same-topic message reports a completed check plus the observed state, classify the turn as troubleshooting attempt_result and emit attempted_action with action, result and outcome; do not reduce the complete check to a generic observation. Map a reported affected population or quantity to affected_scope. Do not duplicate the same action in multiple case updates. Domain scope is strict: mark out_of_scope for independent requests that do not ask for technical support, operation, configuration, troubleshooting, documentation, assets, consumables or processes of the enterprise printing service. Do not treat a public figure, entertainment topic, general knowledge request, copyrighted-content request or other external subject as in scope merely because the message casually adds a printing verb. A bare or contrived association without a concrete technical object, symptom, operation or support goal remains out_of_scope. Out-of-scope turns must set should_retrieve false, needs_clarification false and requested_workflow none."""
REQUIRED={"requested_workflow","user_act","intent","topic_relation","domain_relevance","current_goal","goal_complete","goal_updates","case_updates","needs_clarification","clarification_target","should_retrieve","confidence","reasoning_summary"}
ALLOWED=set(REQUIRED)|{"canonical_subject","subject_origin","reference_relation"}
ALIASES={"clarification_needed":"needs_clarification","clarification_question":"clarification_target"}
class ConversationUnderstanding:
 def __init__(self,gateway,max_tokens=300):self.gateway=gateway;self.max_tokens=max(220,min(420,int(max_tokens)));self.last_provider_result={};self.contract_valid=False;self.validation_error=None;self.normalization={"removed_goal_update_keys":[]}
 def _degraded(self,memory,reason):return TurnUnderstanding("follow_up",memory.pending_goal.intent or "unknown","same_topic","uncertain",memory.pending_goal.summary or memory.active_topic or "",False,{},[],False,None,False,0.,reason,True)
 def _degraded_current(self,message,reason):
  text=" ".join(str(message or "").split());low=text.casefold()
  intent="conceptual" if any(x in low for x in ("document","informacion","información","que muestra","qué muestra","analizar")) else "procedural" if any(x in low for x in ("como ","cómo ","procedimiento","instalar","configurar","asignar","actualizar")) else "unknown"
  return TurnUnderstanding("new_request",intent,"new_topic","in_scope" if intent!="unknown" else "uncertain",text,False,{"subject":text} if text else {},[],False,None,True,0.35,reason,True)
 def _parse(self,text):
  text=str(text or "").strip();a=text.find("{");b=text.rfind("}")
  if a<0 or b<a:raise ValueError("json_object_missing")
  raw=json.loads(text[a:b+1])
  if not isinstance(raw,dict) or not raw:raise ValueError("empty_object")
  aliases={}
  for src,dst in ALIASES.items():
   if dst not in raw and src in raw:raw[dst]=raw[src];aliases[src]=dst
  updates=raw.get("goal_updates")
  if isinstance(updates,list):
   facts=[str(x.get("fact") or x.get("value") or "").strip() for x in updates if isinstance(x,dict)]
   facts=[x for x in facts if x];raw["goal_updates"]={"subject":facts[0]} if facts else {}
   if facts and not raw.get("current_goal"):raw["current_goal"]=facts[0]
   aliases["goal_updates:list"]="goal_updates:dict"
  probe=" ".join((str(raw.get("current_goal") or ""),str(raw.get("goal_updates") or ""))).casefold()
  raw.setdefault("user_act","new_request");raw.setdefault("intent","conceptual" if any(x in probe for x in ("document","analiz","informacion","información")) else "procedural")
  raw.setdefault("topic_relation","new_topic");raw.setdefault("domain_relevance","in_scope");raw.setdefault("current_goal",probe.strip() or "Atender la solicitud actual")
  raw.setdefault("canonical_subject",None);raw.setdefault("subject_origin",None);raw.setdefault("reference_relation","none");raw.setdefault("requested_workflow","none");raw.setdefault("goal_complete",False);raw.setdefault("goal_updates",{});raw.setdefault("case_updates",[]);raw.setdefault("needs_clarification",False);raw.setdefault("clarification_target",None);raw.setdefault("should_retrieve",True);raw.setdefault("confidence",0.75);raw.setdefault("reasoning_summary","provider_payload_normalized")
  missing=REQUIRED-set(raw)
  if missing:raise ValueError("missing_fields:"+",".join(sorted(missing)))
  for legacy in ALIASES:raw.pop(legacy,None)
  unknown=sorted(set(raw)-ALLOWED);clean={key:raw[key] for key in ALLOWED}
  raw_goal_updates=dict(clean.get("goal_updates") or {})
  provider_goal_status=str(raw_goal_updates.get("status") or raw_goal_updates.get("goal_status") or "").strip().casefold()
  clean["goal_updates"],removed=normalize_goal_updates(raw_goal_updates)
  self.normalization={"removed_goal_update_keys":removed,"schema_aliases":aliases,"removed_unknown_fields":unknown,"contract_repaired":bool(aliases or unknown),"provider_goal_status":provider_goal_status}
  return TurnUnderstanding(**clean)
 def _normalize(self,x,memory):
  corrections=[]
  # Recover a non-operational conversational opening before the generic conceptual
  # policy can force retrieval. This uses only semantic structure, never user words.
  goal_updates=dict(x.goal_updates or {})
  social_shape=(
   x.user_act=="new_request" and x.intent=="conceptual" and bool(x.goal_complete)
   and not x.case_updates and not x.needs_clarification
   and not str(x.canonical_subject or "").strip()
   and str(x.reference_relation or "none")=="none"
   and str(x.requested_workflow or "none")=="none"
   and set(goal_updates).issubset({"operation"})
  )
  if social_shape:
   x.user_act="social";x.intent="social";x.topic_relation="same_topic" if (memory.active_topic or memory.active_subject) else "no_topic"
   x.should_retrieve=False;x.goal_updates={};x.case_updates=[];x.needs_clarification=False;x.clarification_target=None
   corrections.append("semantic_non_operational_opening_recovered_before_retrieval_policy")
  # Recover a completed acknowledgement/closure before an inherited technical intent
  # can turn it into a follow-up. This relies only on structured semantic state.
  # A pending assistant question, workflow, case fact, retrieval request or new technical
  # detail keeps the turn operational. The inherited subject alone is not new work.
  normalized_updates=dict(x.goal_updates or {})
  closure_shape=(
   x.user_act in {"answer_to_question","follow_up"}
   and not memory.last_assistant_question and bool(x.goal_complete)
   and not x.should_retrieve and not x.case_updates and not x.needs_clarification
   and str(x.requested_workflow or "none")=="none"
   and str(self.normalization.get("provider_goal_status") or "").casefold() in {"complete","completed","closed"}
   and set(normalized_updates).issubset({"subject"})
  )
  if closure_shape:
   x.user_act="social";x.intent="social";x.topic_relation="same_topic" if (memory.active_topic or memory.active_subject) else "no_topic"
   x.should_retrieve=False;x.goal_updates={};x.case_updates=[];x.needs_clarification=False;x.clarification_target=None
   x.canonical_subject=None;x.subject_origin=None;x.reference_relation="none"
   corrections.append("semantic_non_operational_closure_recovered_before_followup_policy")
  if x.user_act=="answer_to_question" and not memory.last_assistant_question:x.user_act="follow_up" if memory.active_topic else "new_request";corrections.append("answer_without_pending_question_normalized")
  if x.user_act=="request_elaboration":
   if not memory.active_topic and not memory.last_assistant_question:x.user_act="new_request";x.topic_relation="new_topic";corrections.append("orphan_elaboration_to_new_request")
   elif x.topic_relation=="new_topic":x.user_act="new_request";x.should_retrieve=True;corrections.append("provider_new_topic_preserved")
   else:x.topic_relation="same_topic";x.should_retrieve=True;corrections.append("referential_operational_retrieval_enforced")
  operational_case_types={"symptom","reported_failure","new_case","attempted_action","attempt_result","affected_scope"}
  case_types={str(item.get("type") or "") for item in (x.case_updates or []) if isinstance(item,dict)}
  if x.intent=="conceptual" and case_types.intersection(operational_case_types):
   x.intent="troubleshooting";x.should_retrieve=True;corrections.append("case_signal_promoted_operational_intent")
  if x.intent=="conceptual" and x.domain_relevance=="in_scope":x.needs_clarification=False;x.clarification_target=None;x.should_retrieve=True
  if x.needs_clarification and not str(x.clarification_target or "").strip():x.needs_clarification=False;corrections.append("empty_clarification_suppressed")
  if x.intent=="troubleshooting":
   present={str(a.get("type") or "") for a in x.case_updates}
   for key in ("symptom","observation","affected_scope","attempted_action","attempt_result"):
    value=str((x.goal_updates or {}).get(key) or "").strip()
    if value and key not in present:x.case_updates.append({"type":key,"value":value});corrections.append("goal_fact_promoted_to_case:"+key)
  self.normalization.setdefault("structural_corrections",[]);self.normalization["structural_corrections"].extend(corrections);return x
 def interpret(self,message,memory):
  from app.llm_gateway.models import LLMRequest
  req=lambda payload,purpose:self.gateway.complete(LLMRequest([{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],purpose,self.max_tokens,0.,UNDERSTANDING_SCHEMA))
  r=req({"message":message,"context":compact_context(memory)},"agent_core_v2_clean_understanding");self.last_provider_result=r.to_dict();self.contract_valid=False;self.validation_error=None;self.normalization={"removed_goal_update_keys":[]}
  if not r.ok:self.validation_error="provider_error:"+str(r.error_code or "unknown");return self._degraded_current(message,self.validation_error)
  try:
   if str(getattr(r,"finish_reason","") or "").casefold() in {"length","max_tokens"}:raise ValueError("understanding_output_truncated")
   x=self._parse(r.text);self.contract_valid=True;return self._normalize(x,memory)
  except Exception as exc:
   first_error=str(exc);retry=req({"message":message,"context":compact_context(memory),"invalid_output":str(r.text or "")[:4000],"validation_error":first_error,"instruction":"Return only a complete JSON object matching the schema without extra fields."},"agent_core_v2_clean_understanding_repair")
   self.last_provider_result={"initial":r.to_dict(),"repair":retry.to_dict(),"repair_attempted":True};self.normalization={"removed_goal_update_keys":[],"repair_attempted":True,"repair_succeeded":False}
   if retry.ok:
    try:
     if str(getattr(retry,"finish_reason","") or "").casefold() in {"length","max_tokens"}:raise ValueError("understanding_repair_output_truncated")
     x=self._parse(retry.text);self.contract_valid=True;self.validation_error=None;self.normalization["repair_attempted"]=True;self.normalization["repair_succeeded"]=True;return self._normalize(x,memory)
    except Exception as retry_exc:
     self.normalization["repair_truncated"]=str(getattr(retry,"finish_reason","") or "").casefold() in {"length","max_tokens"}
     self.validation_error=str(retry_exc)
   else:self.validation_error="repair_provider_error:"+str(retry.error_code or "unknown")
   return self._degraded_current(message,"invalid_understanding:"+str(self.validation_error or first_error))
