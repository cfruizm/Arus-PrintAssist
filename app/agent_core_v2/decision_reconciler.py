from __future__ import annotations
from .models import CanonicalDecision,InterpreterProposal,ConversationState

CANCEL_ACTS={"cancel","cancel_all"};RESUME_ACTS={"resume_escalation"}
RETRIEVAL_INTENTS={"conceptual","procedural","troubleshooting","requirements","architecture","warranty"}

class DecisionReconciler:
    def reconcile(self,message,proposal:InterpreterProposal,state:ConversationState,entities):
        action=proposal.requested_action;reasons=[];confidence=max(0,min(1,float(proposal.confidence)))
        if proposal.conversation_act in CANCEL_ACTS or proposal.intent=="cancel":action="cancel_all";reasons.append("global_cancel_has_priority")
        elif proposal.conversation_act in RESUME_ACTS or proposal.intent=="resume":action="resume_escalation";reasons.append("explicit_resume")
        elif state.escalation.status=="collecting" and proposal.topic_relation=="independent_question":action="suspend_escalation";reasons.append("independent_question_suspends_escalation")
        elif proposal.topic_relation=="new_topic":reasons.append("explicit_topic_transition")
        if action=="retrieve" and proposal.intent not in RETRIEVAL_INTENTS:action="ask_clarification";reasons.append("retrieval_not_valid_for_intent")
        if action in {"record_case_detail","record_attempt","record_attempt_result"} and confidence<.7:action="ask_clarification";reasons.append("low_confidence_blocks_state_mutation")
        requires=action=="retrieve"
        allowed=action in {"record_case_detail","record_attempt","record_attempt_result","start_escalation","continue_escalation","suspend_escalation","resume_escalation","cancel_all","switch_topic"} or proposal.topic_relation=="new_topic"
        return CanonicalDecision(action,proposal.intent,proposal.conversation_act,proposal.topic_relation,entities,list(proposal.facts),proposal.clarification_question,confidence,reasons,allowed,requires)
