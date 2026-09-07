from .models import CanonicalDecision
RETRIEVAL_INTENTS={"conceptual","procedural","troubleshooting","requirements","architecture","warranty"}
class DecisionReconciler:
 def reconcile(self,p,state,entities):
  action=p.requested_action;intent=p.intent;reasons=[]
  if p.conversation_act in {"capability","social","farewell"}:action="respond_directly";reasons.append("nontechnical_conversation")
  if p.conversation_act=="cancel" or intent=="cancel":action="cancel_all"
  if action=="retrieve" and intent not in RETRIEVAL_INTENTS:action="ask_clarification";reasons.append("invalid_retrieval_intent")
  mutate=action in {"record_case_detail","record_attempt","record_attempt_result","start_escalation","continue_escalation","suspend_escalation","resume_escalation","cancel_all"} or p.topic_relation=="new_topic"
  return CanonicalDecision(action,intent,p.conversation_act,p.topic_relation,entities,p.facts,p.clarification_question,p.confidence,reasons,mutate,action=="retrieve")
