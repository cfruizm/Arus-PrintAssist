from .models import AgentDecision
class ConversationPolicy:
 def decide(self,u,m):
  if u.domain_relevance=="out_of_scope":return AgentDecision("redirect_scope","independent_out_of_scope")
  if u.intent=="cancel" or u.user_act=="cancel":return AgentDecision("cancel","explicit_cancel")
  if u.intent=="escalation" or u.user_act=="escalation":return AgentDecision("offer_escalation","explicit_escalation")
  if u.degraded:return AgentDecision("degraded_continue","provider_degraded")
  if u.intent=="troubleshooting":
   if u.needs_clarification and u.clarification_target:return AgentDecision("ask_one_question","material_missing_detail",True,u.clarification_target)
   return AgentDecision("diagnose","active_failure")
  if u.needs_clarification and u.clarification_target:return AgentDecision("ask_one_question","material_missing_detail",True,u.clarification_target)
  if u.should_retrieve:return AgentDecision("defer_to_retrieval","retrieval_required_in_next_phase")
  return AgentDecision("answer","goal_understood")
