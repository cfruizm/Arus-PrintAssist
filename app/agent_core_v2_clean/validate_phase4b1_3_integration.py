from copy import deepcopy
from .agent import CleanConversationalAgent
from .models import ConversationMemory, PendingGoal, SupportCase, TurnUnderstanding, AgentDecision, AgentResponse


class UnderstandingStub:
    contract_valid = True
    validation_error = None
    normalization = {}
    last_provider_result = {"calls": 1}
    def interpret(self, message, memory):
        return TurnUnderstanding(
            user_act="new_request", intent="conceptual", topic_relation="new_topic",
            domain_relevance="in_scope", current_goal="Greet and open conversation",
            goal_complete=False, goal_updates={}, case_updates=[], needs_clarification=False,
            clarification_target=None, should_retrieve=False, confidence=.98,
            reasoning_summary="Non-operational conversational opening", degraded=False,
            canonical_subject=None, subject_origin="none", reference_relation="none",
            requested_workflow="none",
        )


class PolicyStub:
    def decide(self, u, memory):
        return AgentDecision("respond", "social")


class ResponseStub:
    last_provider_result = None
    calls = 0
    def compose(self, message, memory, u, decision):
        self.calls += 1
        if u.intent == "social":
            self.last_provider_result = {"skipped": True, "reason": "social_turn_uses_deterministic_terminal_response"}
            return AgentResponse("Estoy aquí para ayudarte.", "deterministic_social", False)
        raise AssertionError("technical generation must not run")


def run():
    memory = ConversationMemory(
        active_topic="Existing topic", active_subject="Existing document",
        pending_goal=PendingGoal("Existing goal", "conceptual", {"document":"Existing document"}, None, "active"),
        support_case=SupportCase(status="diagnosing", subject="Existing document", symptoms=["Existing symptom"]),
        turn_number=5, subject_history=[{"subject":"Earlier document","turn":2}],
    )
    before = deepcopy(memory.to_dict())
    response = ResponseStub()
    result = CleanConversationalAgent(UnderstandingStub(), PolicyStub(), response).process("lateral turn", memory)
    after = memory.to_dict()
    checks = {
        "normalized_social": result["understanding"]["intent"] == "social" and result["understanding"]["user_act"] == "social",
        "retrieval_disabled": result["understanding"]["should_retrieve"] is False and result["retrieval"]["enabled"] is False,
        "deterministic_response": result["answer"]["mode"] == "deterministic_social",
        "one_response_path": response.calls == 1 and result["provider_trace"]["response"]["skipped"] is True,
        "topic_preserved": after["active_topic"] == before["active_topic"],
        "subject_preserved": after["active_subject"] == before["active_subject"],
        "goal_preserved": after["pending_goal"] == before["pending_goal"],
        "case_preserved": after["support_case"] == before["support_case"],
        "history_preserved": after["subject_history"] == before["subject_history"],
        "only_turn_counter_changes": after["turn_number"] == before["turn_number"] + 1,
        "pre_reconciliation_terminal": "social_turn_pre_reconciliation_terminal" in result["goal_update_normalization"]["structural_corrections"],
    }
    failed = [k for k,v in checks.items() if not v]
    return {"passed":len(checks)-len(failed),"failed":len(failed),"checks":checks}


if __name__ == "__main__":
    import json
    result=run();print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(1 if result["failed"] else 0)
