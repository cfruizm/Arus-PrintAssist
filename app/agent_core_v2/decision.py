from .models import CanonicalDecision
RETRIEVAL={"conceptual","procedural","troubleshooting","requirements","architecture","warranty"}
class DecisionReconciler:
 def reconcile(self,p,s,entities):
  a=p.requested_action;why=[]
  if p.intent=="cancel" or p.conversation_act in {"cancel","cancel_all"}:a="cancel_all";why.append("cancel_priority")
  elif p.intent=="resume":a="resume_escalation"
  elif s.escalation.status=="collecting" and p.topic_relation=="independent_question":a="suspend_escalation";why.append("pause_for_independent_question")
  if a=="retrieve" and p.intent not in RETRIEVAL:a="ask_clarification";why.append("invalid_retrieval_intent")
  mutate=a in {"record_case_detail","record_attempt","record_attempt_result","start_escalation","continue_escalation","suspend_escalation","resume_escalation","cancel_all"} or p.topic_relation=="new_topic"
  if mutate and p.confidence<.7:a="ask_clarification";mutate=False;why.append("low_confidence")
  return CanonicalDecision(a,p.intent,p.conversation_act,p.topic_relation,entities,p.facts,p.clarification_question,p.confidence,why,mutate,a=="retrieve")
