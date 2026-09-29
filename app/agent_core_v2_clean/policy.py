from .models import AgentDecision

WORKFLOW_ACTIONS={
 "start_escalation":"offer_escalation",
 "continue_escalation":"continue_escalation",
 "suspend_escalation":"continue_escalation",
 "resume_escalation":"continue_escalation",
 "cancel_escalation":"cancel",
 "confirm_escalation":"continue_escalation",
}

class ConversationPolicy:
 def decide(self,u,m):
  intent=str(u.intent or "").casefold();act=str(u.user_act or "").casefold();workflow=str(getattr(u,"requested_workflow","none") or "none").casefold()
  # Operational workflow is independent from technical intent and has routing authority.
  if workflow in WORKFLOW_ACTIONS:
   action=WORKFLOW_ACTIONS[workflow]
   return AgentDecision(action,"semantic_workflow_contract:"+workflow)
  if intent in {"social","meta","capabilities"} or act in {"social","request_capabilities"}:return AgentDecision("answer","conversational_turn_no_retrieval")
  if u.domain_relevance=="out_of_scope":return AgentDecision("redirect_scope","independent_out_of_scope")
  if getattr(m,"escalation",None) and m.escalation.status in {"collecting","review"}:return AgentDecision("continue_escalation","active_escalation_flow")
  if u.needs_clarification and u.clarification_target:return AgentDecision("ask_one_question","material_missing_detail",True,u.clarification_target)
  if intent=="cancel" or act=="cancel":return AgentDecision("cancel","explicit_cancel")
  # Backward compatibility for providers that still return the legacy escalation act.
  if intent=="escalation" or act=="escalation":return AgentDecision("offer_escalation","legacy_explicit_escalation")
  if u.degraded:return AgentDecision("degraded_continue","provider_degraded")
  if m.support_case.status=="diagnosing" and u.should_retrieve and act in {"request_elaboration","answer_to_question","attempt_result"}:return AgentDecision("diagnose_with_retrieval","active_case_next_guidance_requires_grounding")
  if intent=="troubleshooting" and u.should_retrieve:return AgentDecision("diagnose_with_retrieval","grounded_troubleshooting_requested")
  if intent=="troubleshooting":return AgentDecision("diagnose","active_failure")
  if u.should_retrieve:return AgentDecision("defer_to_retrieval","retrieval_required_in_next_phase")
  return AgentDecision("answer","goal_understood")
