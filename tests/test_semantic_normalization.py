from app.agent_core.conversation_act_runtime import sanitize_semantic_decision


def test_non_retrieve_mode_removes_retrieval_request():
    model={"conversation_act":"report_failed_attempt","response_mode":"deterministic","retrieval_request":{"question":"otra acción"},"clarification_question":"¿qué hiciste?","state_updates":[{"type":"attempt_result","value":"failed","confidence":0.95}]}
    derived={"response_mode":"deterministic","requires_retrieval":False}
    result=sanitize_semantic_decision(model,derived,{"failed_actions":[],"resolution_status":None})
    assert result["normalized_decision"]["retrieval_request"] is None
    assert result["normalized_decision"]["clarification_question"] is None
    assert set(result["fields_sanitized"]) == {"retrieval_request","clarification_question"}
