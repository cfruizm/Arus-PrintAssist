from .models import CanonicalDecision
TECHNICAL_INTENTS={"conceptual","procedural","troubleshooting","requirements","architecture","warranty"}
LATERAL_ACTS={"capability","social","farewell"}
class DecisionReconciler:
 def reconcile(self,p,state,entities):
  action=p.requested_action;intent=p.intent;relation=p.topic_relation;reasons=[]
  active_products={x.canonical_id for x in state.active_topic.products};current_products={x.canonical_id for x in entities if x.kind=="product"};current_processes={x.canonical_id for x in entities if x.kind=="process"}
  active_context=bool(active_products or state.active_topic.processes)
  generic_clarification=(not p.clarification_question) or p.clarification_question.strip() in {"¿Podrías ampliar la solicitud?","Podrías ampliar la solicitud?"}
  if p.conversation_act in LATERAL_ACTS:action="respond_directly";relation="independent_question";entities=[];reasons.append("lateral_act_preserves_topic")
  elif p.conversation_act=="clarification" and intent in TECHNICAL_INTENTS and generic_clarification and (entities or active_context):
   action="retrieve";reasons.append("repair_false_clarification_from_resolved_context")
  elif p.conversation_act=="technical_request" and intent in TECHNICAL_INTENTS:action="retrieve";reasons.append("documentation_first")
  elif action=="retrieve" and intent not in TECHNICAL_INTENTS:action="ask_clarification";reasons.append("invalid_document_request")
  if p.conversation_act=="technical_request":
   if current_processes and not current_products and relation in {"new_topic","independent_question"}:relation="new_topic";reasons.append("new_process_detaches_previous_product")
   elif active_products and current_products and current_products!=active_products and relation=="new_topic":reasons.append("semantic_product_change")
   elif current_products and relation=="same_topic":reasons.append("semantic_alias_or_component_continuity")
  if p.conversation_act=="cancel" or intent=="cancel":action="cancel_all"
  active_intent=getattr(state.active_topic,"intent",None);intent_changed=p.conversation_act=="technical_request" and intent in TECHNICAL_INTENTS and intent!=active_intent
  mutate=(relation in {"new_topic","return_to_previous"} or action in {"record_case_detail","record_attempt","record_attempt_result","start_escalation","continue_escalation","suspend_escalation","resume_escalation","cancel_all"} or intent_changed) and p.conversation_act not in LATERAL_ACTS
  return CanonicalDecision(action,intent,p.conversation_act,relation,entities,p.facts,p.clarification_question,p.confidence,reasons,mutate,action=="retrieve")
