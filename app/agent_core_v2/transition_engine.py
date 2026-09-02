from __future__ import annotations
from .models import ConversationState,CanonicalDecision,Attempt
from .state import unique_append,unique_entity,reset_active_topic,cancel_all,norm

class TransitionEngine:
    def apply(self,state:ConversationState,decision:CanonicalDecision):
        audit={"applied":[],"skipped":[]};state.turn_number+=1
        if decision.action=="cancel_all":cancel_all(state);audit["applied"].append("cancel_all");return audit
        if decision.topic_relation=="new_topic":reset_active_topic(state,f"topic-{state.turn_number}");audit["applied"].append("switch_topic")
        if decision.action=="start_escalation":state.escalation.status="collecting";audit["applied"].append("start_escalation")
        elif decision.action=="suspend_escalation":state.escalation.status="suspended";state.escalation.suspended_reason="independent_question";audit["applied"].append("suspend_escalation")
        elif decision.action=="resume_escalation":state.escalation.status="collecting";state.escalation.suspended_reason=None;audit["applied"].append("resume_escalation")
        for entity in decision.entities:
            target=state.active_topic.products if entity.kind=="product" else state.active_topic.components if entity.kind=="component" else state.active_topic.processes
            (audit["applied"] if unique_entity(target,entity) else audit["skipped"]).append(f"entity:{entity.canonical_id}")
        for fact in decision.facts:
            typ=str(fact.get("type") or "");value=str(fact.get("value") or "").strip()
            if typ=="symptom" and unique_append(state.technical_case.symptoms,value):state.technical_case.status="diagnosing";audit["applied"].append("symptom")
            elif typ=="attempted_action":
                if not any(norm(x.action)==norm(value) for x in state.technical_case.attempts):state.technical_case.attempts.append(Attempt(value,None,state.turn_number));audit["applied"].append("attempted_action")
                else:audit["skipped"].append("duplicate_attempt")
            elif typ=="attempt_result" and state.technical_case.attempts:
                result=str(value);last=state.technical_case.attempts[-1]
                if norm(last.result)!=norm(result):last.result=result;state.technical_case.resolution_status="resolved" if norm(result) in {"resolved","successful"} else "unresolved";state.technical_case.status=state.technical_case.resolution_status;audit["applied"].append("attempt_result")
                else:audit["skipped"].append("duplicate_attempt_result")
            elif typ=="affected_scope":state.technical_case.affected_scope=value;audit["applied"].append("affected_scope")
            elif typ=="evidence" and unique_append(state.technical_case.evidence,value):audit["applied"].append("evidence")
        state.active_topic.intent=decision.intent;state.last_action=decision.action
        return audit
