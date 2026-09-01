from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from app.agent_core.router_models import ContextFact, RouterShadowState

ALLOWED_UPDATE_TYPES = {
    "product", "process", "symptom", "attempted_action", "attempt_result",
    "affected_scope", "error_message", "evidence", "technical_context",
    "resolution_status",
}
RESOLVED_VALUES = {"resolved", "successful", "success", "solved", "resuelto", "exitoso"}
FAILED_VALUES = {"failed", "failure", "unresolved", "fallido", "no_resuelto"}


def _norm(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _contains(values: list[Any], candidate: Any) -> bool:
    wanted = _norm(candidate)
    return bool(wanted) and any(_norm(value) == wanted for value in values)


def _fact_exists(facts: list[ContextFact], fact_type: str, value: str) -> bool:
    return any(
        _norm(getattr(fact, "fact_type", "")) == _norm(fact_type)
        and _norm(getattr(fact, "value", "")) == _norm(value)
        for fact in facts
    )


def _append_fact(case, fact_type: str, value: str, confidence: float) -> bool:
    if _fact_exists(case.context_facts, fact_type, value):
        return False
    case.context_facts.append(
        ContextFact(
            fact_type=fact_type,
            value=value,
            confidence=confidence,
            source="semantic_orchestrator",
            metadata={"application_mode": "controlled_state_update"},
        )
    )
    return True


def _event(update: dict, status: str, reason: str | None = None) -> dict:
    result = {
        "type": str(update.get("type") or ""),
        "value": str(update.get("value") or ""),
        "confidence": float(update.get("confidence") or 0.0),
        "status": status,
    }
    if reason:
        result["reason"] = reason
    return result


def apply_semantic_state_updates(
    router_state: RouterShadowState,
    normalized_decision: dict,
    *,
    minimum_confidence: float = 0.75,
) -> dict:
    """Apply only validated semantic facts to RouterShadowState.

    This function never controls routing, retrieval, escalation, or the visible
    response. It is deterministic, confidence-gated, idempotent, and fail-closed.
    """
    report = {
        "attempted": 0,
        "applied": [],
        "skipped": [],
        "changed": False,
        "minimum_confidence": minimum_confidence,
    }
    if not isinstance(normalized_decision, dict):
        report["skipped"].append({"status": "skipped", "reason": "decision_not_object"})
        return report

    updates = normalized_decision.get("state_updates") or []
    if normalized_decision.get("topic_shift"):
        report["skipped"].append({"status": "skipped", "reason": "topic_shift_not_applied_in_this_stage"})

    topic = router_state.topic
    case = router_state.technical_case

    for raw in updates:
        report["attempted"] += 1
        if not isinstance(raw, dict):
            report["skipped"].append({"status": "skipped", "reason": "update_not_object"})
            continue
        update = dict(raw)
        update_type = str(update.get("type") or "").strip()
        value = str(update.get("value") or "").strip()[:400]
        try:
            confidence = max(0.0, min(1.0, float(update.get("confidence", 0.0))))
        except Exception:
            confidence = 0.0
        update["confidence"] = confidence

        if update_type not in ALLOWED_UPDATE_TYPES:
            report["skipped"].append(_event(update, "skipped", "unsupported_type"))
            continue
        if not value:
            report["skipped"].append(_event(update, "skipped", "empty_value"))
            continue
        if confidence < minimum_confidence:
            report["skipped"].append(_event(update, "skipped", "below_confidence_threshold"))
            continue

        applied = False
        if update_type == "product":
            if not _contains(topic.products, value):
                topic.products.append(value)
                applied = True
        elif update_type == "process":
            if not _contains(topic.processes, value):
                topic.processes.append(value)
                applied = True
        elif update_type == "symptom":
            if not _contains(case.symptoms, value):
                case.symptoms.append(value)
                applied = True
            if case.status in {"idle", "intake"}:
                case.status = "diagnosing"
        elif update_type == "attempted_action":
            if not _contains(case.attempted_actions, value):
                case.attempted_actions.append(value)
                applied = True
        elif update_type == "attempt_result":
            normalized_value = _norm(value)
            if normalized_value in FAILED_VALUES:
                case.resolution_status = "unresolved"
                if case.status not in {"resolved", "completed"}:
                    case.status = "unresolved"
                if case.attempted_actions:
                    last_action = case.attempted_actions[-1]
                    if not _contains(case.failed_actions, last_action):
                        case.failed_actions.append(last_action)
                        applied = True
                applied = _append_fact(case, "attempt_result", "failed", confidence) or applied
            elif normalized_value in RESOLVED_VALUES:
                case.resolution_status = "resolved"
                case.status = "resolved"
                applied = _append_fact(case, "attempt_result", "successful", confidence)
            else:
                applied = _append_fact(case, "attempt_result", value, confidence)
        elif update_type == "affected_scope":
            if _norm(case.affected_users) != _norm(value):
                case.affected_users = value
                applied = True
        elif update_type == "resolution_status":
            normalized_value = _norm(value)
            canonical = "resolved" if normalized_value in RESOLVED_VALUES else (
                "unresolved" if normalized_value in FAILED_VALUES else value
            )
            if _norm(case.resolution_status) != _norm(canonical):
                case.resolution_status = canonical
                case.status = "resolved" if canonical == "resolved" else (
                    "unresolved" if canonical == "unresolved" else case.status
                )
                applied = True
        elif update_type == "evidence":
            if not _contains(case.evidence, value):
                case.evidence.append(value)
                applied = True
        else:
            applied = _append_fact(case, update_type, value, confidence)

        if applied:
            report["applied"].append(_event(update, "applied"))
            report["changed"] = True
        else:
            report["skipped"].append(_event(update, "skipped", "duplicate_or_no_change"))

    router_state.conversation.last_user_act = str(normalized_decision.get("conversation_act") or "") or None
    return report


def state_snapshot(router_state: RouterShadowState) -> dict:
    if is_dataclass(router_state):
        return asdict(router_state)
    return {"repr": repr(router_state)}
