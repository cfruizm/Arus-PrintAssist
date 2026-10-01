from copy import deepcopy
from .agent import _is_structurally_social
from .models import TurnUnderstanding


def u(**overrides):
    data = dict(
        user_act="new_request", intent="conceptual", topic_relation="new_topic",
        domain_relevance="in_scope", current_goal="", goal_complete=False,
        goal_updates={}, case_updates=[], needs_clarification=False,
        clarification_target=None, should_retrieve=False, confidence=.9,
        reasoning_summary="", degraded=False, canonical_subject=None,
        subject_origin=None, reference_relation="none", requested_workflow="none",
    )
    data.update(overrides)
    return TurnUnderstanding(**data)


def run():
    checks = {}
    checks["explicit_social"] = _is_structurally_social(u(user_act="social", intent="social"))[0]
    checks["provider_label_drift"] = _is_structurally_social(u())[0]
    checks["technical_retrieval_not_social"] = not _is_structurally_social(u(should_retrieve=True))[0]
    checks["subject_not_social"] = not _is_structurally_social(u(canonical_subject="Servicio"))[0]
    checks["case_update_not_social"] = not _is_structurally_social(u(case_updates=[{"type":"symptom","value":"falla"}]))[0]
    checks["reference_not_social"] = not _is_structurally_social(u(reference_relation="current_subject"))[0]
    checks["workflow_not_social"] = not _is_structurally_social(u(requested_workflow="escalation"))[0]
    checks["out_of_scope_not_social"] = not _is_structurally_social(u(domain_relevance="out_of_scope"))[0]
    failed = [name for name, ok in checks.items() if not ok]
    return {"passed": len(checks)-len(failed), "failed": len(failed), "checks": checks}


if __name__ == "__main__":
    import json
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(1 if result["failed"] else 0)
