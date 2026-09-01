from app.agent_core.router_models import RouterShadowState
from app.agent_core.semantic_state_runtime import apply_semantic_state_updates


def decision(*updates, act="provide_case_detail", topic_shift=False):
    return {"conversation_act": act, "state_updates": list(updates), "topic_shift": topic_shift}


def update(kind, value, confidence=0.95):
    return {"type": kind, "value": value, "confidence": confidence}


def test_applies_transversal_case_facts():
    state=RouterShadowState()
    report=apply_semantic_state_updates(state,decision(
        update("product","PaperCut MF"), update("symptom","Trabajos no visibles"),
        update("affected_scope","multiple_users"), update("error_message","Sin mensaje"),
    ))
    assert report["changed"] is True
    assert state.topic.products == ["PaperCut MF"]
    assert state.technical_case.symptoms == ["Trabajos no visibles"]
    assert state.technical_case.affected_users == "multiple_users"
    assert state.technical_case.status == "diagnosing"
    assert state.technical_case.context_facts[0].fact_type == "error_message"


def test_failed_attempt_marks_last_action_once():
    state=RouterShadowState(); state.technical_case.status="diagnosing"
    state.technical_case.attempted_actions=["Reinicio del proveedor de impresión"]
    payload=decision(update("attempt_result","failed"),act="report_failed_attempt")
    first=apply_semantic_state_updates(state,payload)
    second=apply_semantic_state_updates(state,payload)
    assert first["changed"] is True
    assert second["changed"] is False
    assert state.technical_case.failed_actions == ["Reinicio del proveedor de impresión"]
    assert state.technical_case.resolution_status == "unresolved"


def test_below_threshold_is_rejected():
    state=RouterShadowState()
    report=apply_semantic_state_updates(state,decision(update("symptom","dato débil",0.4)))
    assert report["changed"] is False
    assert not state.technical_case.symptoms
    assert report["skipped"][0]["reason"] == "below_confidence_threshold"


def test_deduplicates_case_insensitively():
    state=RouterShadowState(); state.topic.products=["PaperCut MF"]
    report=apply_semantic_state_updates(state,decision(update("product"," papercut mf ")))
    assert report["changed"] is False
    assert state.topic.products == ["PaperCut MF"]


def test_topic_shift_does_not_clear_previous_case():
    state=RouterShadowState(); state.topic.products=["PaperCut MF"]
    report=apply_semantic_state_updates(state,decision(topic_shift=True))
    assert state.topic.products == ["PaperCut MF"]
    assert report["skipped"][0]["reason"] == "topic_shift_not_applied_in_this_stage"


def test_resolution_is_applied_without_retrieval_control():
    state=RouterShadowState(); state.technical_case.status="diagnosing"
    report=apply_semantic_state_updates(state,decision(update("resolution_status","resolved")))
    assert report["changed"] is True
    assert state.technical_case.status == "resolved"
    assert state.technical_case.resolution_status == "resolved"
