from __future__ import annotations

import json
from .documented_fact_coverage import ensure_enumerated_fact_coverage
from .documented_answer import DocumentedAnswerComposer
from app.llm_gateway.models import LLMResult


class _Gateway:
    def complete(self, request):
        return LLMResult(
            ok=True,
            text="La evidencia indica que el identificador que cumple la propiedad es 443. [R1]",
            provider="test",
            model="test",
            purpose=request.purpose,
            usage={"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
            finish_reason="stop",
        )


def main():
    question = "¿Y cuál de esos elementos utiliza TLS?"
    understanding = {
        "intent": "requirements",
        "canonical_subject": "Producto X",
        "user_act": "request_elaboration",
        "topic_relation": "same_topic",
    }
    evidence = [
        {"id": "R1", "title": "Guide", "page": 5, "source": "guide.pdf", "text": "443 I R TCP Comunicacion web mediante SSL/TLS."},
        {"id": "R2", "title": "Guide", "page": 6, "source": "guide.pdf", "text": "5222 I R TCP Mensajeria segura mediante TLS para control."},
        {"id": "R3", "title": "Guide", "page": 6, "source": "guide.pdf", "text": "3702 UDP Descubrimiento local sin cifrado."},
    ]
    repaired, diagnostic = ensure_enumerated_fact_coverage(
        "La evidencia confirma 443. [R1]", question, understanding, evidence
    )
    complete, complete_diag = ensure_enumerated_fact_coverage(
        "La evidencia confirma 443 [R1] y 5222 [R2].", question, understanding, evidence
    )
    unrelated, unrelated_diag = ensure_enumerated_fact_coverage(
        "Respuesta general [R1]", "Explica el producto", understanding, evidence
    )
    retrieval = {"evidence_verdict": {"selected_evidence": evidence}, "_answer_context": {}}
    composer = DocumentedAnswerComposer(_Gateway(), 760)
    response = composer.compose(question, understanding, retrieval)
    checks = {
        "omitted_fact_repaired": "5222" in repaired and "[R2]" in repaired and diagnostic["repaired"],
        "complete_answer_not_modified": complete == "La evidencia confirma 443 [R1] y 5222 [R2]." and not complete_diag["repaired"],
        "unrelated_question_not_modified": unrelated == "Respuesta general [R1]" and not unrelated_diag["repaired"],
        "composer_publishes_missing_fact": "5222" in response.text and "[R2]" in response.text,
        "composer_citations_valid": composer.validation.get("citations_valid") is True,
        "coverage_diagnostic_present": composer.validation.get("documented_fact_coverage", {}).get("repaired") is True,
        "no_product_specific_rule": all(x not in (open(__file__.replace("validate_phase4b1_3.py", "documented_fact_coverage.py"), encoding="utf-8").read() + open(__file__.replace("validate_phase4b1_3.py", "documented_answer.py"), encoding="utf-8").read()).casefold() for x in ("papercut", "hp sds", "find-me")),
        "format_updated": "henkia_support_assist_4b1_3" in open(__file__.replace("validate_phase4b1_3.py", "lab_session.py"), encoding="utf-8").read(),
    }
    result = {"phase": "4B.1.3", "passed": sum(checks.values()), "failed": len(checks) - sum(checks.values()), "checks": checks}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
