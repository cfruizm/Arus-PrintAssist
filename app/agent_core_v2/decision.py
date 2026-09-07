from .models import CanonicalDecision

TECHNICAL_INTENTS={"conceptual","procedural","troubleshooting","requirements","architecture","warranty"}
LATERAL_ACTS={"capability","social","farewell"}

class DecisionReconciler:
 def reconcile(self,p,state,entities):
  action=p.requested_action;intent=p.intent;relation=p.topic_relation;reasons=[]
  active_products={x.canonical_id for x in state.active_topic.products}
  current_products={x.canonical_id for x in entities if x.kind=="product"}
  explicit_new_product=bool(active_products and current_products and not current_products.issubset(active_products))

  if p.conversation_act in LATERAL_ACTS:
   action="respond_directly";relation="independent_question";entities=[];reasons.append("lateral_act_preserves_technical_topic")
  elif intent in TECHNICAL_INTENTS and p.confidence>=0.6:
   action="retrieve";reasons.append("documentation_first_for_confident_technical_intent")
  elif action=="retrieve" and intent not in TECHNICAL_INTENTS:
   action="ask_clarification";reasons.append("invalid_document_request")

  if explicit_new_product and p.conversation_act=="technical_request":
   relation="new_topic";reasons.append("canonical_product_change_requires_new_topic")

  if p.conversation_act=="cancel" or intent=="cancel":action="cancel_all"
  active_intent=getattr(state.active_topic,"intent",None)
  intent_changed=action=="retrieve" and intent in TECHNICAL_INTENTS and intent!=active_intent
  mutate=(relation in {"new_topic","return_to_previous"} or action in {"record_case_detail","record_attempt","record_attempt_result","start_escalation","continue_escalation","suspend_escalation","resume_escalation","cancel_all"} or intent_changed) and p.conversation_act not in LATERAL_ACTS
  return CanonicalDecision(action,intent,p.conversation_act,relation,entities,p.facts,p.clarification_question,p.confidence,reasons,mutate,action=="retrieve")
