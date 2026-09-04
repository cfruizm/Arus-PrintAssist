# Patch helper module used by the existing multiturn lab checkpoint.
def scope_checkpoint(turn):
    evidence=turn.get("evidence") or {};answer=turn.get("answer") or {};coverage=evidence.get("coverage") or {};citables=evidence.get("citable") or []
    checks={
      "citable_sources_have_supported_claims":all(bool((x.get("semantic_assessment") or {}).get("supported_claims")) for x in citables),
      "direct_sources_have_same_scope":all((x.get("semantic_assessment") or {}).get("scope_relation")=="same" for x in evidence.get("direct") or []),
      "narrower_only_declared_in_answer":not coverage.get("all_applicable_sources_narrower") or answer.get("coverage_mode")=="narrower_only",
      "knowledge_used_consistent":not answer.get("contextual_sources_used") or bool(answer.get("knowledge_used")),
    }
    return {"checks":checks,"failed_checks":[k for k,v in checks.items() if not v],"passed":all(checks.values())}
