from .models import CanonicalDecision
TECHNICAL={"conceptual","procedural","troubleshooting","requirements","architecture","warranty"}
LATERAL={"capability","social","farewell"}
class DecisionReconciler:
 def reconcile(self,p,state,entities):
  action=p.requested_action;intent=p.intent;relation=p.topic_relation;reasons=[];active=getattr(getattr(state,"active_topic",None),"intent",None)
  if p.conversation_act in LATERAL:
   action="respond_directly";relation="independent_question";entities=[];reasons.append("lateral_conversation_no_topic_mutation")
  if action=="retrieve" and intent not in TECHNICAL:action="ask_clarification";reasons.append("invalid_document_request")
  if p.conversation_act=="cancel":action="cancel_all"
  # Technical intent is mutable per turn; lateral acts never mutate technical state.
  intent_changed=p.conversation_act=="technical_request" and intent in TECHNICAL and intent!=active
  mutate=(relation in {"new_topic","return_to_previous"} or action in {"record_case_detail","record_attempt","record_attempt_result","start_escalation","continue_escalation","suspend_escalation","resume_escalation","cancel_all"} or intent_changed) and p.conversation_act not in LATERAL
  return CanonicalDecision(action,intent,p.conversation_act,relation,entities,p.facts,p.clarification_question,p.confidence,reasons,mutate,action=="retrieve")
