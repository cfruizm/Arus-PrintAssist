from __future__ import annotations
import json
from .unified_evidence_authority import apply_unified_evidence_verdict
from .semantic_fit import capture_answer_context
from .guidance_integrity import build_guidance_integrity_contract
from .citation_finalizer import finalize_citations


def evidence(rid="R1", text="Validate the queue state and inspect the event log before advancing."):
    return {"id": rid, "title": "Authorized troubleshooting guide", "source": "doc://primary", "page": "1", "text": text, "metadata": {}}


def run():
    prior = {
        "goal": "Diagnose retained print jobs",
        "main_text_excerpt": "The queue remains blocked after connectivity and service validation.",
        "source_identities": ["doc://primary"],
        "source_titles": ["Authorized troubleshooting guide"],
        "cited_evidence": [evidence()],
        "active_document_evidence_ledger": [evidence()],
        "delivered_guidance": [{"action": "Clear pending spool files", "status": "delivered"}],
    }
    raw = {
        "query": {"fields": {
            "topic_relation": "same_topic_refinement", "previous_evidence_role": "primary",
            "user_act": "request_elaboration", "goal": "Diagnose retained print jobs",
            "contextual_operation": "Continue diagnosis", "details": {"operation": "diagnose queue"},
        }},
        "diagnostic_evidence": [evidence()], "_answer_context": prior,
    }
    authorized = apply_unified_evidence_verdict(
        raw, "Continue with the next documented checks without repeating prior guidance",
        {"intent": "troubleshooting", "topic_relation": "same_topic", "user_act": "request_elaboration", "current_goal": "Continue diagnosis"},
    )
    internal_result = {
        "answer": {"text": "### Orientación sugerida\n\n1. Inspect the next reversible condition.", "mode": "controlled_internal_knowledge", "finish_reason": "stop"},
        "retrieval": {"evidence": []},
        "understanding": {"topic_relation": "same_topic", "current_goal": "Continue diagnosis"},
        "document_continuity": {"same_topic": True, "primary": True},
    }
    preserved = capture_answer_context(internal_result, prior)
    contract = build_guidance_integrity_contract({"_answer_context": preserved, "_case_context": {"attempts": []}})
    plan = {"evidence_plan": {"citation_map": {}, "documented_ids": ["R1"], "selected_evidence": [evidence()]}, "response_plan": {"allow_documented_claims": True}}
    final_text, audit = finalize_citations("Supported statement [R1]. Orphan statement [R5].", plan)
    checks = {
        "referential_followup_uses_accumulated_goal": authorized["evidence_verdict"]["accepted"] is True,
        "primary_document_remains_authorized": authorized["evidence_verdict"]["reason"] in {"primary_document_accumulated_goal_relevance", "primary_document_current_turn_relevance"},
        "internal_fallback_preserves_document_ledger": preserved["source_identities"] == ["doc://primary"] and preserved["historical_document_context_preserved"] is True,
        "delivered_guidance_survives_fallback": contract["assistant_delivered_guidance"][0]["action"] == "Clear pending spool files",
        "orphan_citation_removed": "[R5]" not in final_text and audit.valid is True,
        "validated_citation_remains": "[R1]" in final_text and audit.cited_ids == ["R1"],
    }
    failed = [name for name, ok in checks.items() if not ok]
    return {"phase": "4B.3.4", "status": "passed" if not failed else "failed", "passed": len(checks)-len(failed), "failed": len(failed), "failed_checks": failed, "checks": checks}


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "passed" else 1)
