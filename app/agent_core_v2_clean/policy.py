from .models import AgentDecision
class ConversationPolicy:
 def decide(self,u,memory):
  if u.domain_relevance=="out_of_scope":return AgentDecision("redirect_scope","independent_out_of_scope")
  if u.user_act=="cancel" or u.intent=="cancel":return AgentDecision("cancel","explicit_cancel")
  if u.user_act=="escalation" or u.intent=="escalation":return AgentDecision("offer_escalation","explicit_escalation")
  if u.intent=="troubleshooting":return AgentDecision("diagnose","active_failure",u.needs_clarification,u.clarification_target)
  if u.needs_clarification:return AgentDecision("ask_one_question","material_missing_detail",True,u.clarification_target)
  return AgentDecision("answer","goal_understood")
